# PostgreSQL cho RAG + LightRAG + MLOps: Research Report

*Generated: 2026-08-10 | Sources: 60+ | Confidence: High (claims đơn nguồn được đánh dấu ⚠)*

> Báo cáo deep-research cho dự án rag-real-estate. Đối chiếu chéo với các ADR trong
> `.claude/CLAUDE.md` — hầu hết quyết định đã chốt của dự án được xác nhận bởi research này,
> và có thêm các khuyến nghị cụ thể về parameter/concurrency/pooling.
> Bổ sung cho `storage-pipeline-research.md` (storage/AGE verdict) và
> `guardrails-roles-mlops-research.md` (security/guardrails/MLOps overview) — file này đào sâu
> PG parameter tuning + LightRAG production tuning + MLOps eval/migration protocol.

---

## Executive Summary

1. **PostgreSQL + pgvector là lựa chọn production hợp lệ cho ≤10M vectors** — 1 hệ thống cho cả business data + vectors, SQL filtering, backup/pg_dump thống nhất. Vượt ngưỡng đó mới cần Qdrant/Milvus riêng ([Citadel Cloud](https://www.citadelcloudmanagement.com/blog/building-production-rag-pipelines-engineers-guide)). Điều này xác nhận ADR "PG single-backend" của dự án.
2. **3 GUC quan trọng nhất cho RAG/pgvector**: `maintenance_work_mem` (8–16GB lúc build HNSW, nếu thiếu → spill disk + build chậm thảm hại), `work_mem` (256MB–1GB cho `<=>` sort), `shared_buffers` (25% RAM). Riêng `hnsw.ef_search` là GUC **session-level** — bị PgBouncer transaction-mode nuốt âm thầm nếu `SET` không phải `SET LOCAL`/`ALTER DATABASE` ([pgvector README](https://github.com/pgvector/pgvector), [rivestack](https://rivestack.io/blog/pgvector-hnsw-vs-ivfflat)).
3. **LightRAG 1.5.6+ có `PGTableGraphStorage`** — graph chạy trên plain PG tables (JSONB + B-tree), KHÔNG cần Apache AGE, chạy được mọi managed PG. Kết nối qua **env vars `POSTGRES_*`** (không có DSN string), LightRAG **tự tạo bảng nhưng không tạo database** (phải `CREATE DATABASE` trước), và **bắt buộc gọi `await rag.initialize_storages()`** ([ProgramingWithCore.md](https://github.com/HKUDS/LightRAG/blob/main/docs/ProgramingWithCore.md)).
4. **Concurrency index là bài toán chính**: `max_parallel_insert ≈ llm_model_max_async / 3`, `embedding_batch_num` cao = giảm số API call + tăng tốc persist vào PG. Over-tune `max_parallel_insert` → xung đột tên entity lúc merge ([LightRAG_concurrent_explain.md](https://github.com/HKUDS/LightRAG/blob/v1.4.13/docs/LightRAG_concurrent_explain.md)).
5. **MLOps: 3 pipeline tách rời** (query / ingestion / evaluation), golden set 50–200 câu **đối xử như code**, gate CI theo delta (không theo absolute mean), **đổi embedding model = database migration** (không phải deploy) — blue-green với shadow index + parity check + giữ index cũ ≥1 tuần ([tianpan.co](https://tianpan.co/blog/2026-04-23-embedding-rotation-database-migration-not-deploy), [llmbestpractices](https://llmbestpractices.com/ai-agents/rag-eval)).

---

## 1. PostgreSQL trong RAG — Parameter tuning

### 1.1 Core GUCs (postgresql.conf)

| GUC | Default | Khuyến nghị RAG | Ghi chú |
|---|---|---|---|
| `shared_buffers` | 128MB | **25% RAM** (dedicated server); RDS/Aurora 30–35% | Static, cần restart. >40% không thắng vì PG dựa cả OS cache. HNSW index phải vừa shared_buffers + OS cache nếu không latency spike ([PG 19 docs](https://www.postgresql.org/docs/19/runtime-config-resource.html), [jacar.es](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/)) |
| `work_mem` | 4MB | **256MB–1GB** | Per-operation (mỗi sort/hash op), nhân với `hash_mem_multiplier` (2.0). Query với N sort × M parallel workers dùng ~12× work_mem → chỉ an toàn khi pooling giữ active connections thấp ([Railway](https://blog.railway.com/p/hosting-postgres-with-pgvector), [TURION](https://turion.ai/blog/pgvector-at-scale-when-postgres-is-enough/)) |
| `maintenance_work_mem` | 64MB | **8–16GB** (lúc build HNSW) | Critical nhất. HNSW build trong memory; thiếu → `NOTICE: hnsw graph no longer fits into maintenance_work_mem` + build chậm bùng nổ. An toàn set cao vì 1 maintenance op/session ([Cybertec](https://www.cybertec-postgresql.com/en/indexing-vectors-in-postgresql/), [TURION](https://turion.ai/blog/pgvector-at-scale-when-postgres-is-enough/)) |
| `max_parallel_maintenance_workers` | 2 | 4–8 (theo cores) | pgvector 0.6.0+ hỗ trợ **parallel HNSW build** ([pgvector README](https://github.com/pgvector/pgvector)) |
| `max_connections` | 100 | 200 + PgBouncer | PG process-per-connection: mỗi backend 1.5–2MB RSS, 10–20MB khi làm việc. App RAG giữ connection idle trong lúc LLM gen 1–30s → pooling bắt buộc ([duckkit.dev](https://duckkit.dev/blog/postgresql-connection-pooling-pgbouncer-guide), [CallSphere](https://callsphere.ai/blog/connection-pooling-ai-applications-pgbouncer-pgpool-application-pools)) |
| `effective_cache_size` | 128MB | **75% RAM** | Chỉ là hint cho planner (index vs seq scan), không allocate memory ([Railway](https://blog.railway.com/p/hosting-postgres-with-pgvector)) |
| `max_wal_size` / `checkpoint_timeout` | 1GB / 5min | **16GB / 15min** | Bulk ingest vector → checkpoint liên tục gây full-page writes thừa. `wal_compression=on` cắt WAL (~1.5x–10x hiệu quả theo EDB ⚠) ([PG WAL docs](https://www.postgresql.org/docs/current/wal-configuration.html), [MonPG](https://monpg.app/blog/postgresql-wal-checkpoint-tuning)) |

### 1.2 pgvector — HNSW (default nên dùng) vs IVFFlat

| Param | Default | Khởi điểm production | Notes |
|---|---|---|---|
| `m` | 16 | 16–32 (tới 48 nếu dim >768 / cần recall ≥0.98) | Build-time, immutable; tăng gấp đôi cost build + index size ([Multigrid](https://multigrid.ai/learn/pgvector-index-tuning)) |
| `ef_construction` | 64 | 64–200 | Build-time; **không ảnh hưởng index size**, chỉ build time; phải ≥ `2*m` ([pgvector README](https://github.com/pgvector/pgvector)) |
| `hnsw.ef_search` | 40 | 40–400, tune theo query | **Query-time GUC — dial recall/latency chính**. Phải ≥ LIMIT. **Bẫy: session-level GUC bị PgBouncer transaction mode nuốt** → dùng `SET LOCAL` trong transaction hoặc `ALTER DATABASE ... SET` ([Multigrid](https://multigrid.ai/learn/pgvector-index-tuning), [rivestack](https://rivestack.io/blog/pgvector-hnsw-vs-ivfflat)) |

**Thứ tự tuning HNSW** (đắt → rẻ): giảm dim vector (lever lớn nhất: 1536→768 giảm nửa index memory + build time) → tăng `ef_construction` (rẻ, không đổi size) → tăng `m` (đắt nhất). `ef_search` tăng trước, free, per-query, không rebuild ([Multigrid](https://multigrid.ai/learn/pgvector-index-tuning)).

**Quy tắc bắt buộc khác:**
- **Opclass phải khớp operator**: `vector_cosine_ops` ↔ `<=>`, `vector_l2_ops` ↔ `<->`, `vector_ip_ops` ↔ `<#>`; lệch → planner âm thầm seq scan. Verify bằng `EXPLAIN (ANALYZE, BUFFERS)` ([docs.digitalocean](https://docs.digitalocean.com/products/vector-databases/postgresql/how-to/index-and-tune/)).
- **HNSW không pre-filter theo WHERE** — filter selective → recall cliff. Mitigation: partial index/partition theo tenant, raise ef_search, hoặc **iterative scans (pgvector 0.8+)** tự scan thêm khi filter làm giảm kết quả ([jacar.es](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/)). **Liên quan trực tiếp lớp filter `effective_date`/`status` của dự án.**
- **`CREATE INDEX CONCURRENTLY`** (pgvector 0.6.0+) để không block writes; build **sau khi bulk load** (insert vào HNSW đã tồn tại chậm hơn nhiều) ([pgvector README](https://github.com/pgvector/pgvector)).
- **HNSW thoái hóa sau nhiều delete/update → `REINDEX INDEX CONCURRENTLY` định kỳ** (weekly off-peak). Một case: xóa 200K stale chunks làm recall giảm 8% trong 2 ngày ([jacar.es](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/)).
- `halfvec` (pgvector 0.7+) ≈ nửa index size, recall gần như không đổi — bật đầu tiên nếu RAM căng ([jacar.es](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/)).

**IVFFlat** — chỉ khi RAM hạn chế hoặc rebuild thường xuyên: `lists` = rows/1000 (≤1M rows) hoặc `sqrt(rows)` (>1M); `ivfflat.probes` khởi điểm = `sqrt(lists)`. **Phải build sau khi load data** (k-means cần data thật), centroid drift → REINDEX ([pgvector README](https://github.com/pgvector/pgvector)).

### 1.3 Connection pooling — BẮT BUỘC cho RAG

**Vì sao**: request RAG mở connection, fetch context, rồi **chờ LLM 1–30s trong khi giữ connection idle**. 50 agent sessions × giữ trong lúc LLM = cạn 100 connections mặc định. Retrieval fan-out 5–15 query song song trong 100ms mỗi request. **KHÔNG bao giờ giữ transaction mở qua LLM/embedding call** — persist request, release connection, gen, re-acquire ([CallSphere](https://callsphere.ai/blog/connection-pooling-ai-applications-pgbouncer-pgpool-application-pools), [tianpan.co](https://tianpan.co/blog/2026-04-17-database-connection-pool-ai-pipeline-bottleneck)).

**PgBouncer `pool_mode = transaction` là consensus** — multiplex hàng nghìn client → vài chục backend. Session mode không giảm backend count ("giải bài toán sai"). Config tham khảo: `max_client_conn = 200–5000`, `default_pool_size = 20–200`, `server_idle_timeout = 60` ([PgBouncer docs](https://www.pgbouncer.org/features), [DevOpsNess](https://www.devopsness.com/blog/database-connection-pooling-at-scale-pgbouncer-rds-proxy-application-pool-2026-04-24)).

**Sizing theo Little's Law**: `pool = requests/sec × avg query duration` + 2–3x margin, giới hạn ~2× DB cores ([CallSphere](https://callsphere.ai/blog/connection-pooling-ai-applications-pgbouncer-pgpool-application-pools)).

**⚠ Trap với pgvector**: `hnsw.ef_search`/`ivfflat.probes` là session GUC — transaction pooling route query sang backend khác → setting bị drop âm thầm. Fix: `SET LOCAL` trong transaction hoặc `ALTER DATABASE ... SET hnsw.ef_search = 80`. Transaction mode cũng phá: prepared statements (`statement_cache_size=0` trong asyncpg), session advisory locks, LISTEN/NOTIFY ([rivestack](https://rivestack.io/blog/pgvector-hnsw-vs-ivfflat), [MonPG](https://monpg.app/blog/postgresql-pgbouncer-transaction-mode-gotchas)).

### 1.4 Managed providers (RDS / Supabase / Neon)

| Provider | Tinh chỉnh được | Hạn chế |
|---|---|---|
| **RDS** | Custom parameter group (static cần reboot). Gần như đủ mọi param: shared_buffers, work_mem, maintenance_work_mem, max_wal_size, wal_compression | RDS Proxy thay PgBouncer (failover + IAM); pgvector preinstalled ([RDS docs](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.Parameters.html)) |
| **Supabase** | CLI+SQL: shared_buffers (restart), work_mem, maintenance_work_mem, effective_cache_size, wal_compression, pg_stat_statements | Cần `POSTGRES_SERVER_SETTINGS=options=reference%3D<project-ref>` cho Supavisor ([Supabase](https://supabase.com/docs/guides/database/custom-postgres-config)) |
| **Neon** | **Không superuser**; instance params (shared_buffers, max_connections...) theo compute size, không đổi được (trừ Scale plan) | Workaround: `ALTER DATABASE ... SET maintenance_work_mem='1GB'` (session-level, cap ~60% RAM compute) ([Neon](https://neon.com/docs/reference/compatibility)) |

**Caveat chung**: pgvector version lệch giữa providers — iterative scans cần 0.8+, HNSW cần 0.5+. Check `pg_available_extensions` trên instance ([pecollective](https://pecollective.com/tools/pgvector/)). NVMe quan trọng khi HNSW index > cache (traversal = random reads) ([rivestack](https://rivestack.io/blog/best-managed-pgvector-providers)).

### 1.5 Backup & observability

- **pg_dump/PITR phủ graph tables y hệt bảng thường** — "1 database, 1 kế hoạch backup" là lý do cốt lõi chọn pgvector ([jacar.es](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/)). **Khớp ADR rule #5 của dự án.**
- **pg_stat_statements**: bật qua `shared_preload_libraries` (restart). Giới hạn: hash cố định (default max=5000 — raise), cumulative, không percentiles. Dùng `stats_since` (PG17+) ([pganalyze](https://pganalyze.com/blog/postgres-in-production-pg-stat-statements-deep-dive-part-1), [boringsql](https://boringsql.com/posts/pg-stat-statements/)).
- **auto_explain**: `log_min_duration=1000`, `log_analyze=on`, `log_buffers=on`, **`log_timing=off`** (per-node timing rất tốn), `compute_query_id=on` để join với pg_stat_statements ([Datapace](https://datapace.ai/blog/pgstat-vs-autoexplain)).
- **Triage slow query**: `log_min_duration_statement` → pg_stat_statements → `EXPLAIN (ANALYZE, BUFFERS)`. Cache hit ratio <95% = index > shared_buffers+cache. Dead-tuple >20% = autovacuum lag → hạ `autovacuum_vacuum_scale_factor` 0.01–0.05 trên bảng vector churn cao ([Netdata](https://www.netdata.cloud/guides/postgres/postgres-slow-queries-diagnosis/)).
- **CI recall-regression test sau mỗi lần bump pgvector version** — "một thay đổi parameter không được âm thầm làm giảm chất lượng" ([jacar.es](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/)).

---

## 2. LightRAG + PostgreSQL — Integration

### 2.1 Bốn storage backends PG (chọn 1 class/role)

| Role | Class | Lưu gì |
|---|---|---|
| KV | `PGKVStorage` | LLM response cache, text chunks, full docs, extraction results, entity-chunk links |
| Vector | `PGVectorStorage` | Embeddings cho chunks/entities/relations (cần pgvector ext — auto `CREATE EXTENSION IF NOT EXISTS vector`) |
| **Graph** | **`PGTableGraphStorage`** (1.5.6+, khuyến nghị) | Graph nodes/edges trên **plain tables** `lightrag_graph_nodes`/`lightrag_graph_edges` (JSONB properties, B-tree indexes) — **KHÔNG AGE, KHÔNG Cypher** |
| Graph (legacy) | `PGGraphStorage` | Graph trong Apache AGE — chậm ~20x, không chạy managed PG |
| Doc status | `PGDocStatusStorage` | Document processing status (pipeline scheduler) |

([ProgramingWithCore.md](https://github.com/HKUDS/LightRAG/blob/main/docs/ProgramingWithCore.md), [PR #3103](https://github.com/HKUDS/LightRAG/pull/3103))

**Multi-tenant**: PG stores thêm cột `workspace` (default `"default"`); graph tables key `(workspace, namespace, id)` với namespace default `chunk_entity_relation`. Override bằng `WORKSPACE` hoặc `POSTGRES_WORKSPACE` ([LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md)).

### 2.2 Kết nối — env vars, KHÔNG có DSN string

```bash
# BẮT BUỘC (validate lúc startup qua check_storage_env_vars)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=rag            # database instance — PHẢI tự tạo trước
POSTGRES_MAX_CONNECTIONS=25      # asyncpg pool max_size (default 25)

# Tuỳ chọn quan trọng
POSTGRES_SSL_MODE=require        # disable|allow|prefer|require|verify-ca|verify-full
POSTGRES_VECTOR_INDEX_TYPE=HNSW  # HNSW | HNSW_HALFVEC | IVFFlat | VCHORDRQ
POSTGRES_HNSW_M=16 / POSTGRES_HNSW_EF=200 / POSTGRES_IVFFLAT_LISTS=100
POSTGRES_UPSERT_MAX_PAYLOAD_BYTES=16777216   # 16 MiB
POSTGRES_UPSERT_MAX_RECORDS_PER_BATCH=200
POSTGRES_CONNECTION_RETRIES=10 / POSTGRES_CONNECTION_RETRY_BACKOFF=3.0
POSTGRES_SERVER_SETTINGS=        # Supabase Supavisor: options=reference%3D<project-ref>
POSTGRES_STATEMENT_CACHE_SIZE=100  # 0 = disable
```

([env.example](https://github.com/HKUDS/LightRAG/blob/main/env.example), [postgres_impl.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/postgres_impl.py))

**Quan trọng**: LightRAG **tự tạo bảng + index + migration** lúc `initialize()` nhưng **KHÔNG tạo database** — phải `CREATE DATABASE` trước. Tất cả PG storages share **1 asyncpg pool** qua `ClientManager` (ref-counted, SSL + retry + workspace tập trung) ([PR #3103](https://github.com/HKUDS/LightRAG/pull/3103)).

### 2.3 Init signature (LightRAG 1.5.x) — ví dụ canonical

```python
rag = LightRAG(
    working_dir=WORKING_DIR,
    llm_model_name="gemini-2.0-flash",
    llm_model_func=llm_model_func,          # BẮT BUỘC (raise ValueError nếu None)
    embedding_func=embedding_func,          # BẮT BUỘC
    embedding_func_max_async=4,
    embedding_batch_num=8,
    llm_model_max_async=2,
    chunk_token_size=1200,
    chunk_overlap_token_size=100,
    # PostgreSQL-backed storages
    graph_storage="PGTableGraphStorage",    # 1.5.6+ thay PGGraphStorage
    vector_storage="PGVectorStorage",
    doc_status_storage="PGDocStatusStorage",
    kv_storage="PGKVStorage",
)
await rag.initialize_storages()   # BẮT BUỘC — tạo bảng, build pool
```

([lightrag_gemini_postgres_demo.py](https://github.com/HKUDS/LightRAG/blob/main/examples/lightrag_gemini_postgres_demo.py), [lightrag.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/lightrag.py))

**Required vs optional**: `llm_model_func` + `embedding_func` + `POSTGRES_*` env = bắt buộc; còn lại optional. `auto_manage_storages_states=True` tự động initialize/finalize. Gọi `await rag.finalize_storages()` trước shutdown. **Sync wrappers (`insert`/`query`) gọi `run_until_complete()` — không gọi được trong running loop; dùng `ainsert`/`aquery` trong async code.**

### 2.4 Parameter ảnh hưởng PG load

| Param | Default | Effect trên PG |
|---|---|---|
| `max_parallel_insert` | 2–3 | # docs xử lý song song; mỗi doc = batched graph/vector writes. ~`llm_model_max_async/3` |
| `embedding_batch_num` | 32 | texts/embedding request; cao = ít API calls + persist PGVector nhanh hơn |
| `embedding_func_max_async` | 16 | concurrent embedding calls → concurrent vector writes |
| `llm_model_max_async` | 4 | concurrent LLM calls (extraction) → drive graph write concurrency |
| `chunk_token_size` | 1200 | # chunks → # entities/relations ghi vào PG |
| `POSTGRES_MAX_CONNECTIONS` | 25 | pool max_size; phải fit dưới server `max_connections` |
| `POSTGRES_UPSERT_MAX_*` / `POSTGRES_DELETE_MAX_*` | 16MiB / 200 / 1000 | batch splitter — giới hạn transaction duration + client memory |

([README](https://github.com/HKUDS/LightRAG/blob/main/README.md), [LightRAG_concurrent_explain.md](https://github.com/HKUDS/LightRAG/blob/v1.4.13/docs/LightRAG_concurrent_explain.md))

### 2.5 Gotchas đã biết (từ GitHub issues)

1. **Connection exhaustion / pool stacking**: nếu các storage KHÔNG share client pool chung → `too many connections` (default PG max 100) rất nhanh. PR đầu tiên của PGTableGraphStorage bypass ClientManager = blocking review finding, đã fix trước khi merge ([PR #3103](https://github.com/HKUDS/LightRAG/pull/3103)).
2. **Concurrent `CREATE INDEX CONCURRENTLY` → deadlock** khi nhiều container init cùng lúc → **init 1 instance trước**, rồi mới launch fleet ([Issue #2112](https://github.com/HKUDS/LightRAG/issues/2112)). PGTableGraphStorage dùng `pg_advisory_xact_lock` quanh DDL.
3. **DDL không idempotent cũ** → `DuplicateTableError` (v1.4.9.9, #2702, fix #2723). Lesson: pin version mới, DDL hiện tại `CREATE TABLE IF NOT EXISTS`.
4. **PG restart → pool stale** (health vẫn 200 nhưng không reconnect). Fix trong v1.4.10+: tenacity retry + pool reset (`POSTGRES_CONNECTION_RETRIES`) ([Issue #2354](https://github.com/HKUDS/LightRAG/issues/2354)).
5. **Event-loop binding**: init storage trên loop A, dùng trên loop B → `RuntimeError: ... bound to a different event loop`. Pattern `asyncio.run(initialize_rag())` đóng loop sau init và được chấp nhận ([Issue #907](https://github.com/HKUDS/LightRAG/issues/907), [PR #2847](https://github.com/HKUDS/LightRAG/pull/2847)).
6. **63-byte identifier limit**: tên bảng vector nhúng model+dims (`LIGHTRAG_VDB_ENTITY_<model>_<dim>d`) có thể vượt → `_safe_index_name()` hash. **Đổi embedding model = xóa bảng vector + re-embed toàn bộ** (PG hard-code dims lúc CREATE TABLE) ([postgres_impl.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/postgres_impl.py)).
7. **`PGTableGraphStorage` vs `PGGraphStorage` không migration in-place** — đọc cùng `POSTGRES_*` env nhưng lưu khác nơi; đổi = re-index (LLM cache có thể giữ) ([LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md)).
8. **Edge canonicalization**: `src_id=min(a,b), tgt_id=max(a,b)` bằng Python min/max (SQL LEAST/GREATEST lệch trên non-ASCII non-C collation → duplicate edges) ([pgtable_impl.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/pgtable_impl.py)).

---

## 3. LightRAG production best practices

### 3.1 Deployment

- **`lightrag-gunicorn`** = production mode (Gunicorn + Uvicorn multiprocess; **không hỗ trợ Windows**). `--workers 1` default; rule ≤ 2×cores+1. `preload_app=True` để storage locks init ở master trước fork; `on_exit` gọi `finalize_share_data()` ([LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md)).
- **⚠ Behavior change mới (PR #3253)**: dưới multi-worker, mọi `MAX_ASYNC_*` giờ là **total cross-worker** (không phải `MAX_ASYNC × workers`). Pin version gần đây.
- **Pipeline indexing chạy trên 1 worker**; parallelism trong indexing đến từ async, không phải worker count.
- `.env` phải nằm ở startup directory; **đổi .env cần restart terminal** (env inject lúc boot). Sau khi seed `rag_storage/` lúc container đang chạy phải restart (server giữ state boot-time).
- Storage **locked ở lần upload đầu** — đổi storage = re-index ([LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md)).
- **Security**: HOST=0.0.0.0 mà không `LIGHTRAG_API_KEY`/`AUTH_ACCOUNTS` = server mở toang. `WHITELIST_PATHS=/health,/api/*` giữ Ollama-compat routes không auth — narrow xuống `/health` nếu expose network ([env.example](https://raw.githubusercontent.com/HKUDS/LightRAG/main/env.example)).
- Admission control: `MAX_PENDING_DOCUMENTS` (HTTP 429 + Retry-After), `MAX_REQUEST_BODY_BYTES`, `MAX_UPLOAD_SIZE`.

### 3.2 Performance tuning (indexing throughput)

- **Concurrency math**: chunk concurrency lý thuyết = `max_parallel_insert × llm_model_max_async`; phần lớn LLM requests xếp queue ưu tiên (user queries > merge > extraction) ([LightRAG_concurrent_explain.md](https://github.com/HKUDS/LightRAG/blob/v1.4.13/docs/LightRAG_concurrent_explain.md)).
- **Config đã chạy được**: GPT-4.1-mini: `MAX_ASYNC=6`, `MAX_PARALLEL_INSERT=3`, `EMBEDDING_FUNC_MAX_ASYNC=8`, `EMBEDDING_BATCH_NUM=16` → **<15s/chunk**; target <30s/chunk ([issue #2425](https://github.com/HKUDS/LightRAG/issues/2425)). Server README: `MAX_ASYNC_LLM=8`, `MPI=3`, `EMB_ASYNC=16`, `BATCH=32`.
- **Timeout extraction = 2×** config (`EXTRACT_LLM_TIMEOUT=300` → 600s thực). Sizing rule: `max_output_tokens < LLM_TIMEOUT × tokens_per_second`. **Legal docs (bảng, citations → nhiều entity) dễ timeout** → cap `OPENAI_LLM_MAX_TOKENS`/`MAX_EXTRACTION_RECORDS`/`MAX_EXTRACTION_ENTITIES` ([LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md)).
- **`ENTITY_EXTRACTION_USE_JSON=true`** cho model nhỏ (gồm qwen local) — ổn định hơn, chậm hơn; `json_repair` là hard dep ([PyPI](https://pypi.org/project/lightrag-hku/1.5.5/)).

### 3.3 Incremental update (6 tháng/lần — case của dự án)

**Cơ chế**: doc mới chạy pipeline → local subgraph → **merge vào graph hiện có** (union nodes/edges), không rebuild. Đây là lợi thế quyết định vs GraphRAG (mỗi update phải regenerate toàn bộ community summaries) ([arXiv 2410.05779](https://arxiv.org/abs/2410.05779v3)).

**API surface**: `ainsert` (full pipeline) · `ainsert_custom`/`insert_custom_kg` (pre-extracted KG — batch ops, 342K records: ~64K awaits → ~6) · `apipeline_enqueue_documents` + `apipeline_process_enqueue_documents` (background enqueue) · `merge_entities` (dedup/alias) ([PR #2910](https://github.com/HKUDS/LightRAG/pull/2910)).

**Update doc đã tồn tại (answer chính thức từ #2219)**: *"phải xóa doc cũ trước, rồi upload bản mới. Trong lúc xóa, LightRAG dùng LLM caching để reconstruct entities/relationships bị ảnh hưởng. Chia file thành đơn vị nhỏ hơn cải thiện đáng kể hiệu quả update."* **Upload bị reject nếu trùng filename** — delete trước khi re-upload. **Không set `delete_llm_cache=true`** nếu muốn delete rẻ ([issue #2219](https://github.com/HKUDS/LightRAG/issues/2219)).

**Best practice cho update 6 tháng**:
1. Doc mới/sửa đổi → `ainsert` batch incremental (không rebuild).
2. Doc hết hiệu lực/thay thế → `adelete_by_doc_id` (giữ LLM cache) rồi re-insert.
3. **Batch deletions cùng nhau** — deferred KG rebuild chạy 1 lần (85-doc batch trước có ~75× redundant LLM calls, PR #2819).
4. Giữ `kv_store_llm_response_cache.json` khi clear data.
5. Chạy golden-set regression sau mỗi batch (ADR rule #4).

### 3.4 Query modes & token budget

- **`mix` mode (recommended)** = KG + vector chunks; `hybrid` = local+global merged; `local`/`global` cho 1 phía; `naive` = vector-only. Trong `mix`, vector search dùng `top_k` giảm (`min(10, top_k)`) vì KG đã cấu trúc ([DeepWiki](https://deepwiki.com/HKUDS/LightRAG/2.3-retrieval-and-query-modes), [Neo4j](https://neo4j.com/blog/developer/under-the-covers-with-lightrag-retrieval/)).
- **Quy tắc token**: `MAX_ENTITY_TOKENS + MAX_RELATION_TOKENS < MAX_TOTAL_TOKENS`; chunk tokens = phần còn lại ([env.example](https://raw.githubusercontent.com/HKUDS/LightRAG/main/env.example)).
- **Legal recommendation**: `mix` + rerank, `TOP_K` 20–60, `CHUNK_TOP_K` 10–20, `MAX_TOTAL_TOKENS` **8–12k** (giữ context tight cho citation grounding). ⚠ Defaults docs (6000/8000/30000) lệch code constants v1.4.15 (1000/1000/4000) — verify lúc implement.
- **Rerank**: `RERANK_BINDING` = `null`(off)|`cohere`|`jina`|`aliyun`. **qwen3-rerank (aibox) phải config `RERANK_BINDING=cohere`** (endpoint Cohere-style flat), KHÔNG phải aliyun — xác nhận quyết định `generic_rerank_api response_format="standard"` của dự án. `MIN_RERANK_SCORE` 0.6+ nếu LLM không mạnh (= confidence filter), `MAX_ASYNC_RERANK=4`, thêm 1–2s latency — deploy local. Rerank models **swap được bất cứ lúc nào** (query-phase only) ([env.example](https://raw.githubusercontent.com/HKUDS/LightRAG/main/env.example), [rerank.py](https://raw.githubusercontent.com/HKUDS/LightRAG/HEAD/lightrag/rerank.py)).
- `RELATED_CHUNK_NUMBER=5`, `KG_CHUNK_PICK_METHOD` (VECTOR|WEIGHT), `ENABLE_LLM_CACHE` (query cache, disabled khi streaming).

### 3.5 Pitfalls phổ biến

1. **`RuntimeError: This event loop is already running`** — sync wrappers trong FastAPI/Jupyter. Fix: `a*` coroutines hoặc `nest_asyncio.apply()` ([issue #907](https://github.com/HKUDS/LightRAG/issues/907)).
2. **Rate limits**: retry 3×; monitor backend logs cho retry count; tăng `llm_model_max_async` chỉ tới khi concurrency provider plateau ([issue #2264](https://github.com/HKUDS/LightRAG/issues/2264)).
3. **Over-tuned `MAX_PARALLEL_INSERT`** → naming conflicts entity lúc merge + in-flight cache multi-GB; giữ ≤10 và ≈ `llm_model_max_async/3`.
4. **Rerank silently off**: `RERANK_BINDING=null` là default — rerank off kể cả khi set host/model ([PR #1993](https://github.com/HKUDS/LightRAG/pull/1993)).
5. **Startup ordering** trong docker-compose: `depends_on: condition: service_healthy` cho PG/Neo4j ([Jon Roosevelt](https://jonroosevelt.com/blog/production-rag-system-phi4-lightrag/)).
6. **Gunicorn multi-worker + macOS + Docling** = hard incompatibility (fork + PyTorch crash).

---

## 4. MLOps cho RAG — Architecture & thực hành

### 4.1 Architecture — "3 pipeline, đừng coi RAG là 1 pipeline"

| Pipeline | Chức năng | Note |
|---|---|---|
| **Query** | query understanding → rewrite → hybrid retrieval → rerank → context assembly → LLM → response validation → citations | Stateless, horizontally scalable |
| **Ingestion** | parse → clean → chunk → metadata enrich → embed → upsert → index optimize | Queue-driven (không cron), idempotent qua content-hash point IDs |
| **Evaluation** | golden-set regression, online sampling | Chạy riêng, CI/CD |

([Citadel Cloud](https://www.citadelcloudmanagement.com/blog/building-production-rag-pipelines-engineers-guide), [NomadX](https://kubernetes.ae/production-rag-stack-kubernetes-reference-architecture/))

**Nguyên tắc layer**: orchestration giữ mỏng/stateless để A/B retrieval strategy không cần đổi app; **không co-locate embedding model với inference cluster** (cascading latency). **Hybrid retrieval (BM25 + dense) + RRF là production default** — pure vector trượt chính xác trên entity names/error codes ([BigDataBoutique](https://bigdataboutique.com/blog/rag-pipeline-end-to-end-architecture-guide)). **Rerank broad → generate narrow**: retrieve top-50–100, rerank, pass top-3–5.

**GraphRAG/LightRAG trong bức tranh 2026**: GraphRAG = situational (multi-hop/corpus-wide questions), **không incremental indexing** — LightRAG thắng cho corpus đổi (~6 tháng). Chạy Basic Search (plain vector) làm A/B control trước khi build graph. **Graph bị decay 15–20%/quarter** (⚠ single-source) → cần freshness SLA riêng cho graph artifact; evaluate 3 thứ riêng: graph quality / retrieval quality / end-to-end answer quality ([June Feng](https://medium.com/data-science-at-microsoft/graphrag-beyond-the-demo-lessons-from-the-trenches-add83180f849), [tianpan.co](https://tianpan.co/blog/2026-04-09-graphrag-production-when-vector-search-hits-ceiling)).

### 4.2 Evaluation & golden sets

**4 metrics chuẩn** ([RAGAS paper](https://aclanthology.org/2024.eacl-demo.16.pdf), [uatgpt.com](https://uatgpt.com/ai-development-workflows/rag-evaluation-framework/)):
- **Faithfulness** — % claims có trong retrieved context (**bắt hallucination**; quan trọng nhất cho legal)
- **Answer relevance** — answer có trả lời đúng câu hỏi không
- **Context precision** — có bao nhiêu chunk retrieved là liên quan (over-retrieval)
- **Context recall** — retrieved đủ chunks cần thiết không (cần ground-truth doc IDs)

**Framework positioning 2026**: chạy **2 tools — 1 trong CI, 1 production** ([Particula](https://particula.tech/blog/deepeval-vs-ragas-vs-trulens-rag-evaluation-stack)):
- **RAGAS** — 4 metrics reference-free, nhanh nhất, cho experiment/attribution
- **DeepEval** — pytest-native assertions, **tốt nhất cho CI/CD regression gates**
- **TruLens/Arize Phoenix** — OpenTelemetry tracing, span-level failure localization, chạy trên live traffic

**Golden set**: 50–200 Q&A pairs; **50 là floor**. Mỗi row: `question`, `gold_chunk_ids[]` (context recall bắt buộc), `gold_answer`, `slice_tag`. **Đối xử như code**: version, review trong PR, không sửa row để test pass. Feed production failures về set — vòng production→eval giữ gate trung thực ([llmbestpractices](https://llmbestpractices.com/ai-agents/rag-eval), [kartik-nvjk](https://dev.to/kartik-nvjk/how-i-set-up-rag-evals-in-cicd-so-they-actually-catch-regressions-46hb)).

**⚠ Thực hành critical**: **gate trên unsupported-claim-count = 0, không phải aggregate ≥ threshold** — faithfulness aggregate 0.91 có thể chứa 1 claim hallucinated. Aggregate che giấu misattribution ([uatgpt.com](https://uatgpt.com/ai-development-workflows/rag-evaluation-framework/)). **Trực tiếp áp dụng cho legal hallucinate ~1/6.**

**Regression pipeline** (cho mỗi update 6 tháng):
| Stage | Trigger | Gate |
|---|---|---|
| Smoke test | Mỗi PR | 20 câu, faithfulness ≥ 0.80, < 3 min |
| Full eval | Release candidate | 4 metrics ≥ baseline − 2% |
| Weekly sweep | Cron | Trend vs 4-week rolling baseline |
| Production sampled | Continuous 0.5–10% | LLM-judge rubric; citation validity 100% |

**Gate theo delta (Welch's t-test), không theo mean**; pin judge model + temperature=0; **version manifest mỗi eval run** (prompt hash, embedder, top_k, chunk size, reranker, corpus snapshot, judge config) — triage regression = diff manifests ([qaskills](https://qaskills.sh/blog/rag-regression-testing-guide), [Galtea](https://galtea.ai/blog/automated-llm-evaluation-building-a-ci-cd-quality-gate-that-actually-runs)).

**⚠ Calibrate LLM judge với human labels** — legal/medical: wrong-but-plausible answer vẫn score faithful; RAGAS không phân biệt "relevant nhưng factually wrong chunk" (limit cơ bản) ([Anyscale](https://docs.anyscale.com/rag/evaluation), [Axiomlogica](https://axiomlogica.com/ai-ml/ragas-vs-trulens-vs-deepeval-vs-open-rag-eval)).

### 4.3 Monitoring & observability

**Langfuse vs Arize Phoenix** ([qaskills](https://qaskills.sh/blog/langfuse-vs-arize-phoenix), [LLMTools](https://llmtools.cc/blog/langfuse-vs-arize-phoenix/)):

| | Langfuse | Arize Phoenix |
|---|---|---|
| Mạnh | Production platform: prompt mgmt, cost dashboards ($/trace), online evals | Local-first RAG debugging, retrieval/embedding views, 50+ evals free |
| License | MIT core | Server ELv2 (source-available) |
| Backend | PG + ClickHouse + Redis + S3 | SQLite (default) hoặc PG |
| Standard | OTLP (HTTP) | OpenTelemetry + **OpenInference** native |

**Chọn**: Phoenix cho team nhỏ / chẩn đoán retrieval (live <1 phút); Langfuse khi 10+ team cần cost tracking bằng $. **Opik** (Apache-2.0) là option thứ 3.

**Trace gì**: query, retrieved chunks (kèm scores), cited sources, model versions (embedding/reranker/LLM), per-step latency. **OpenInference span kinds**: `AGENT/LLM/TOOL/RETRIEVER/RERANKER/CHAIN/GUARDRAIL/EVALUATOR/EMBEDDING/PROMPT` — một OpenInference trace vẫn là OTLP trace hợp lệ (vendor-neutral) ([Arize](https://arize.com/resources/ai-agent-tracing-evaluation/)).

**Alerting thresholds** (khởi điểm, recalibrate theo domain):
| Metric | Alert |
|---|---|
| P95 end-to-end latency | > 5s |
| Retrieval empty rate | > 5% (missing content/index) |
| **Hallucination rate (sampled)** | **> 8%** |
| LLM token cost/query | > $0.05 |
| Abstention ("I don't know") rate | > 30% → index coverage problem |
| Rubric rolling mean | drop 2–5 điểm kéo dài 15–60 min |

([Citadel Cloud](https://www.citadelcloudmanagement.com/blog/building-production-rag-pipelines-engineers-guide), [prabhaharanv](https://github.com/prabhaharanv/production-hybrid-rag))

### 4.4 CI/CD & data versioning — "đổi embedding model = database migration"

**Lesson cốt lõi 2026**: đổi embedding model = **full data migration** — vectors mới ở manifold khác, cosine similarity với vectors cũ vô nghĩa; query trộn old+new trả nonsense mà **không dashboard nào flag** ("green dashboard là cái bẫy" — latency/error phẳng trong khi retrieval sụp âm thầm) ([tianpan.co](https://tianpan.co/blog/2026-04-23-embedding-rotation-database-migration-not-deploy), [dreaming.press](https://dreaming.press/posts/how-to-migrate-embedding-models-in-production.html)). **Xác nhận 100% ADR rule #1 và #8 của dự án.**

**Playbook blue-green cho vectors**:
1. **Shadow index**: build index mới song song (`embedding_v2` column + `CREATE INDEX CONCURRENTLY`, hoặc namespace/collection mới). Populate từ source text (embeddings không round-trip được).
2. **Dual-write**: mọi doc mới embed qua CẢ 2 model trong cùng transaction (per-doc advisory lock) — freeze delta = 0 khi backfill lịch sử.
3. **Parity check**: gửi queries sang cả 2 index; target 60–80% top-5 overlap trên golden set (1 practitioner dùng 82%; Jaccard ≥ 0.92 là khởi điểm).
4. **Cut over atomically** qua alias (`docs_index_current` → index mới) — rollback = flip feature-flag, không phải restore.
5. **Giữ index cũ ≥ 1 tuần** (đủ 1 business cycle) — drop sớm biến rollback 90s thành re-embed nhiều ngày.
6. **Dưới vài trăm nghìn chunks**: bỏ dual-write, maintenance window rẻ hơn. Chi phí re-embed giờ là hours+dollars; **cái giá thật là quality collapse âm thầm giữa backfill** ([dev.to dual-write](https://dev.to/gabrielanhaia/rag-re-indexing-without-downtime-a-dual-write-pattern-for-embeddings-2bn5), [tianpan.co](https://tianpan.co/blog/2026-07-05-retiring-an-embedding-model-reindex-without-downtime)).

**CI/CD cho RAG**: retrieval config (chunk size, overlap, top-k, threshold, rerank) = **code, phải version + review**. Eval trong CI mỗi PR (trên index subset, không full re-index): block nếu recall drop > 5% hoặc P95 latency tăng > 200ms. Deploy gates: retrieval validation → index warm-up benchmark (P95 ≤ 150ms, MRR ≥ 0.82 ⚠) → canary 5% traffic ~30 min → giữ snapshot index 24h với restore < 5 min ([dev.to CI/CD](https://dev.to/nolanvale/building-a-cicd-pipeline-for-your-enterprise-ai-system-2fo8), [AiOpsVista](https://aiopsvista.com/blog/production-rag-architecture-blueprint)). **Trigger scoping**: chỉ chạy eval khi prompt/model config/retrieval config/corpus đổi — tránh eval fatigue ([Galtea](https://galtea.ai/blog/automated-llm-evaluation-building-a-ci-cd-quality-gate-that-actually-runs)).

### 4.5 Serving & scaling

- **Async everywhere**: FastAPI + `psycopg_pool.AsyncConnectionPool` (min_size 2–20) trong lifespan; mở connection mới/request = lãng phí 10–50ms ([BuildRAG](https://buildrag.com/tutorials/advanced-rag/serving-rag-api/)).
- **Không block event loop trên inference**: tách retrieval (CPU) khỏi generation (GPU) qua task queue (Redis Streams/Celery) khi traffic cao; polling result qua SSE. Monolith async thực dụng cho team < 3 — decomposition chỉ trả tiền > ~1K req/min ([Markaicode](https://markaicode.com/architecture/rag-architecture-with-fastapi/)).
- **Pre-warm models** lúc startup (lifespan) — 7B LLM cold start > 20–30s ([Markaicode](https://markaicode.com/architecture/rag-architecture-with-fastapi/)).
- **Embedding cache (Redis, SHA256 query, TTL ~3600s)** — "nguyên nhân phổ biến nhất của RAG production incidents là thiếu dedicated embedding cache"; 40–62% p95 latency reduction (⚠ single-source) ([Markaicode cache](https://markaicode.com/architecture/fastapi-rag-architecture/)). Semantic cache cho repeated queries = lever cost/latency cao nhất sau prompt caching.
- **Rate limiting**: slowapi (per-IP) + Redis fixed-window counters (cross-worker). Retries exponential backoff, circuit breakers, bounded timeouts (LLM tới 120s) ([BuildRAG](https://buildrag.com/tutorials/advanced-rag/serving-rag-api/), [prabhaharanv](https://github.com/prabhaharanv/production-hybrid-rag)).
- **Cost control**: model routing theo complexity (cheap model cho Q&A đơn giản, mạnh hơn cho complex reasoning — qua LLM gateway/LiteLLM); hard per-user daily token/cost budgets; funnel retrieval 5–8 chunks (context tokens dominate generation cost); track **cost/query là first-class metric** ([Ragnight](https://ragnight.com/blog/architecture-rag-production-guide-complet?locale=en), [KingsleyOnoh](https://www.kingsleyonoh.com/blueprint/multi-agent-rag-platform)).

---

## 5. Khuyến nghị cụ thể cho rag-real-estate

Đối chiếu research với ADR hiện có + điểm mới:

| # | Khuyến nghị | Nguồn |
|---|---|---|
| 1 | **PG single-backend + PGTableGraphStorage được xác nhận** — LightRAG retrieval ~85% là 1-hop point lookups/edge scans, flat SQL thắng trên workload này; AGE wrapper ~100x overhead (⚠ single-author benchmark nhưng khớp PR #3103 ~20x) | [PR #3103](https://github.com/HKUDS/LightRAG/pull/3103), [Latent Space](https://jaesolshin.com/posts/lightrag-pg-rcte/) |
| 2 | **Thêm `POSTGRES_HNSW_EF` + verifier `EXPLAIN`** — bảo đảm `<=>` dùng `vector_cosine_ops` HNSW index, không seq scan | [docs.digitalocean](https://docs.digitalocean.com/products/vector-databases/postgresql/how-to/index-and-tune/) |
| 3 | **PgBouncer transaction mode** quanh PG — mandatory vì pattern giữ connection khi LLM gen; `SET LOCAL`/`ALTER DATABASE` cho ef_search; `statement_cache_size=0` nếu dùng asyncpg | [CallSphere](https://callsphere.ai/blog/connection-pooling-ai-applications-pgbouncer-pgpool-application-pools), [rivestack](https://rivestack.io/blog/pgvector-hnsw-vs-ivfflat) |
| 4 | **`maintenance_work_mem` 8–16GB quanh lúc build HNSW** — đặc biệt khi re-index 6 tháng; `CREATE INDEX CONCURRENTLY`; REINDEX weekly nếu churn cao | [Cybertec](https://www.cybertec-postgresql.com/en/indexing-vectors-in-postgresql/), [jacar.es](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/) |
| 5 | **pgvector iterative scans (0.8+) = công cụ cho filter `effective_date`/`status`** — HNSW không pre-filter; iterative scan tự scan thêm khi filter selective. Nếu pgvector managed < 0.8 → cân nhắc partial index theo status | [pgvector README](https://github.com/pgvector/pgvector) |
| 6 | **Concurrency khởi điểm**: `MAX_ASYNC_LLM=6–8`, `MPI=3`, `EMBEDDING_FUNC_MAX_ASYNC=8–16`, `EMBEDDING_BATCH_NUM=16–32`; `ENTITY_EXTRACTION_USE_JSON=true`; cap extraction records cho legal docs | [issue #2425](https://github.com/HKUDS/LightRAG/issues/2425), [PyPI](https://pypi.org/project/lightrag-hku/1.5.5/) |
| 7 | **Update 6 tháng**: delete-then-reinsert cho doc expired (giữ LLM cache, chia file nhỏ), batch deletions 1 lần, golden-set regression sau mỗi batch, pg_dump trước | [issue #2219](https://github.com/HKUDS/LightRAG/issues/2219), [PR #2819](https://github.com/HKUDS/LightRAG/issues/2819/linked_closing_reference?reference_location=REPO_ISSUES_INDEX) |
| 8 | **Rerank aibox qwen3-rerank = `RERANK_BINDING=cohere`** (endpoint flat Cohere-style), không phải aliyun; `MIN_RERANK_SCORE=0.6+` làm confidence filter | [env.example](https://raw.githubusercontent.com/HKUDS/LightRAG/main/env.example) |
| 9 | **Verifier lúc implement**: defaults token budget lệch giữa docs (6000/8000/30000) và code constants v1.4.15 (1000/1000/4000); `MAX_ASYNC` cross-worker total (PR #3253); `POSTGRES_SERVER_SETTINGS` nếu dùng Supabase | [env.example](https://raw.githubusercontent.com/HKUDS/LightRAG/main/env.example), [PR #3253](https://github.com/HKUDS/LightRAG/pull/3253) |
| 10 | **Eval 2 tools**: RAGAS (hoặc DeepEval) trong CI cho golden-set 50–200 (đã seed 30 — nâng lên 50+, thêm `gold_chunk_ids[]`), Phoenix/Langfuse cho production tracing; **gate unsupported-claim = 0** không phải aggregate | [uatgpt.com](https://uatgpt.com/ai-development-workflows/rag-evaluation-framework/), [Particula](https://particula.tech/blog/deepeval-vs-ragas-vs-trulens-rag-evaluation-stack) |
| 11 | **Đổi embedding model = playbook blue-green** (shadow index → dual-write → parity ≥ 60–80% top-5 → alias cutover → giữ index cũ ≥ 1 tuần). LightRAG có CLI `lightrag-rebuild-vdb` là recovery path sau đổi embedding | [tianpan.co](https://tianpan.co/blog/2026-04-23-embedding-rotation-database-migration-not-deploy), [PyPI](https://pypi.org/project/lightrag-hku/1.5.5/) |
| 12 | **Deployment**: dùng mô hình riêng (FastAPI wrapper quanh LightRAG) với `aquery`/`ainsert` (không sync wrappers); PgBouncer; pool kích thước theo Little's Law; startup ordering qua healthcheck; narrow `WHITELIST_PATHS` về `/health` + API key | [LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md), [CallSphere](https://callsphere.ai/blog/connection-pooling-ai-applications-pgbouncer-pgpool-application-pools) |

---

## Key Takeaways

1. **PostgreSQL + pgvector đủ cho production ≤10M vectors** — giữ 1 DB, 1 backup plan, SQL filtering. 3 GUC quyết định: `maintenance_work_mem` (build HNSW), `work_mem`, `shared_buffers`; cộng `hnsw.ef_search` là dial recall/latency chính (nhớ bẫy session-GUC với PgBouncer).
2. **LightRAG + PG = env vars `POSTGRES_*`** (không DSN), tự tạo bảng nhưng không tạo DB, bắt buộc `initialize_storages()`, 4 storage share 1 pool qua `ClientManager`. `PGTableGraphStorage` (1.5.6+) chạy mọi managed PG.
3. **Concurrency index = `max_parallel_insert ≈ max_async_llm/3`**, `embedding_batch_num` cao hơn = nhanh hơn và ít API call; over-tune → naming conflicts lúc merge.
4. **Update 6 tháng**: delete-then-reinsert (giữ LLM cache) + batch deletions + golden-set regression — LightRAG merge incremental, không rebuild.
5. **MLOps = 3 pipeline tách rời + golden set như code + gate theo delta/claim-level + đổi embedding model là database migration (blue-green)**. Monitoring: Phoenix (local) hoặc Langfuse (production), trace retrieval contexts + cost/query.

## Methodology

Searched 20+ queries (tiếng Anh) qua exa search + WebSearch, fetch 20+ nguồn full (GitHub docs/source, pgvector README/CHANGELOG, PG official docs, Supabase/Neon/RDS docs, production RAG guides 2025–2026). Phân tích 4 sub-question bằng 4 subagent song song. Claims đơn nguồn được đánh dấu ⚠ — đa số là số liệu benchmark cụ thể (cost figure, % reduction) có tính chất tham khảo.

## Sources (chính)

1. [pgvector README](https://github.com/pgvector/pgvector) — HNSW/IVFFlat options, parallel builds, iterative scans, halfvec, opclass rules
2. [PostgreSQL 19 Resource Consumption docs](https://www.postgresql.org/docs/19/runtime-config-resource.html) — shared_buffers/work_mem/maintenance_work_mem chính thức
3. [jacar.es — RAG with Postgres & pgvector in production](https://jacar.es/en/rag-with-postgres-and-pgvector-in-production-from-poc-to-slo/) — production guide: maintenance_work_mem, reindex, recall drift, PgBouncer
4. [Multigrid — pgvector index tuning](https://multigrid.ai/learn/pgvector-index-tuning) — HNSW memory math, tuning order, SET LOCAL trap
5. [CallSphere — Connection pooling for AI applications](https://callsphere.ai/blog/connection-pooling-ai-applications-pgbouncer-pgpool-application-pools) — Little's Law sizing, PgBouncer config
6. [rivestack — pgvector HNSW vs IVFFlat](https://rivestack.io/blog/pgvector-hnsw-vs-ivfflat) — ef_search GUC trap with transaction pooling
7. [Cybertec — Indexing vectors in PostgreSQL](https://www.cybertec-postgresql.com/en/indexing-vectors-in-postgresql/) — maintenance_work_mem spill, parallel HNSW
8. [Supabase custom-postgres-config](https://supabase.com/docs/guides/database/custom-postgres-config) — params configurable
9. [Neon compatibility](https://neon.com/docs/reference/compatibility) — instance vs session params
10. [AWS RDS PostgreSQL parameters](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.Parameters.html) — custom parameter groups
11. [HKUDS/LightRAG — ProgramingWithCore.md](https://github.com/HKUDS/LightRAG/blob/main/docs/ProgramingWithCore.md) — storage table, init, workspace
12. [HKUDS/LightRAG — LightRAG-API-Server.md](https://github.com/HKUDS/LightRAG/blob/main/docs/LightRAG-API-Server.md) — gunicorn, env vars, admission control
13. [HKUDS/LightRAG — env.example](https://github.com/HKUDS/LightRAG/blob/main/env.example) — toàn bộ POSTGRES_*/token/rerank env vars
14. [HKUDS/LightRAG — lightrag.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/lightrag.py) — init signature, initialize/finalize
15. [HKUDS/LightRAG — lightrag/kg/postgres_impl.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/postgres_impl.py) — pool, SSL, retry, table naming, batch limits
16. [HKUDS/LightRAG — lightrag/kg/pgtable_impl.py](https://github.com/HKUDS/LightRAG/blob/main/lightrag/kg/pgtable_impl.py) — PGTableGraphStorage DDL/schema
17. [HKUDS/LightRAG — PR #3103 PGTableGraphStorage](https://github.com/HKUDS/LightRAG/pull/3103) — benchmark ~20x vs AGE, pool review finding
18. [HKUDS/LightRAG — LightRAG_concurrent_explain.md](https://github.com/HKUDS/LightRAG/blob/v1.4.13/docs/LightRAG_concurrent_explain.md) — max_parallel_insert tuning, priority queue
19. [HKUDS/LightRAG — Issue #2219 document update](https://github.com/HKUDS/LightRAG/issues/2219) — delete-then-reupload, LLM cache rebuild
20. [HKUDS/LightRAG — Issue #2425 ingestion latency](https://github.com/HKUDS/LightRAG/issues/2425) — working concurrency config
21. [HKUDS/LightRAG — PR #3253 cross-worker MAX_ASYNC](https://github.com/HKUDS/LightRAG/pull/3253) — behavior change multi-worker
22. [LightRAG paper (arXiv 2410.05779)](https://arxiv.org/abs/2410.05779v3) — incremental update, merge
23. [RAGAS paper (EACL 2024)](https://aclanthology.org/2024.eacl-demo.16.pdf) — 4 metrics methodology
24. [uatgpt — RAG Evaluation Framework](https://uatgpt.com/ai-development-workflows/rag-evaluation-framework/) — claim-level faithfulness, golden set protocol
25. [Particula — DeepEval vs RAGAS vs TruLens](https://particula.tech/blog/deepeval-vs-ragas-vs-trulens-rag-evaluation-stack) — framework positioning, thresholds
26. [tianpan.co — Embedding rotation is a DB migration](https://tianpan.co/blog/2026-04-23-embedding-rotation-database-migration-not-deploy) — blue-green playbook
27. [dev.to — Dual-write re-indexing pattern](https://dev.to/gabrielanhaia/rag-re-indexing-without-downtime-a-dual-write-pattern-for-embeddings-2bn5) — 2-table pgvector, parity check
28. [qaskills — Langfuse vs Arize Phoenix](https://qaskills.sh/blog/langfuse-vs-arize-phoenix) — observability positioning
29. [Citadel Cloud — Building Production RAG Pipelines](https://www.citadelcloudmanagement.com/blog/building-production-rag-pipelines-engineers-guide) — 3 pipelines, alert thresholds
30. [BigDataBoutique — RAG Pipeline Architecture Guide](https://bigdataboutique.com/blog/rag-pipeline-end-to-end-architecture-guide) — 9 stages, hybrid + RRF
31. [June Feng (Microsoft) — GraphRAG beyond the demo](https://medium.com/data-science-at-microsoft/graphrag-beyond-the-demo-lessons-from-the-trenches-add83180f849) — when GraphRAG, 3-level eval
32. [Latent Space — LightRAG without Apache AGE](https://jaesolshin.com/posts/lightrag-pg-rcte/) — ⚠ 85% 1-hop workload, AGE wrapper overhead
33. [Jon Roosevelt — Phi-4 + LightRAG production](https://jonroosevelt.com/blog/production-rag-system-phi4-lightrag/) — HNSW vs IVFFlat, healthcheck ordering
34. [Markaicode — FastAPI RAG architecture](https://markaicode.com/architecture/fastapi-rag-architecture/) — embedding cache, task queue decoupling
35. [BuildRAG — Serving RAG as API](https://buildrag.com/tutorials/advanced-rag/serving-rag-api/) — psycopg_pool, slowapi
