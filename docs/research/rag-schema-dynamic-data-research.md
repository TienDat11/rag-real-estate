# RAG Schema & Dynamic Data — Research Report
*Ngày: 2026-08-10 | Nguồn: ~40 URL (4 subagent deep-research) | Confidence: High (đa nguồn đồng thuận)*

> **Vấn đề**: cấu trúc fields/schema cho chatbot RAG pháp lý + giá BĐS khi dữ liệu biến động
> (pháp lý ~6 tháng, giá theo chiến dịch). Mục tiêu: schema "ngon lành" từ đầu, dễ scale, dễ thay đổi.

---

## Executive Summary

1. **GIÁ KHÔNG nên nằm trong vector index** — dữ liệu thay đổi nhanh (giá, chiết khấu) lấy **live lúc hội thoại** (cache-aside/API), vector index chỉ chứa "ý nghĩa"/tài liệu. Kể cả index incremental hoàn hảo cũng là snapshot — giá đổi hôm qua là stale ngay trong index. (OST, Netguru, Okoone, 247 Labs, Algorithmine)
2. **Pháp lý (chậm)**: interval-validity `effective_from`/`effective_to` (NULL = còn hiệu lực) + **filter-at-retrieval** (hard constraint trong SQL, KHÔNG filter lúc hiển thị — model đã thấy text cũ là rò rỉ). Hỗ trợ as-of-date (hỏi "luật tháng 6/2024").
3. **Quy tắc vàng schema**: "index được → cột, không index riêng → JSONB" + **promote-on-demand** (JSONB → cột khi bắt đầu WHERE trên nó). Cột typed cho field nóng (status, effective_date, tenant/project_id), JSONB cho field biến đổi theo loại (metadata legal/price đặc thù).
4. **`embedding_model` bắt buộc trên mỗi chunk** — đổi model = full re-embed (không incremental được); pattern chuẩn = shadow column + feature flag + golden-set parity (database migration, không phải deploy).
5. **LightRAG update = delete-then-insert** (không merge-in-place); giữ LLM cache; `rebuild_vdb` = đường khôi phục khi đổi embedding.
6. **Eval**: golden set phải version + re-baseline khi corpus đổi (eval invalidation paradox — xác nhận AD-8); pin judge model; thêm drift cases ("bản hiện tại thắng bản cũ", "doc expired không được truy hồi").

---

## 1. Metadata & Chunk Schema (đa nguồn đồng thuận)

### Nhóm field bắt buộc trên mỗi chunk

| Nhóm | Fields | Nguồn |
|---|---|---|
| Identity | `document_id` (ổn định), `chunk_id` (ổn định), `parent_id`, `chunk_index`, `char_start/char_end` | zimmermann, next-gen.cloud |
| Provenance | `source_uri`, `source_type`, `title`, `author`, `section_path` (breadcrumb), `page_number` | llmbestpractices, samuelochoa, stackai |
| Temporal | `created_at`, `updated_at`, `ingested_at`, `valid_from`/`valid_to` | reintech, dailybitsbyai |
| Versioning | `document_version`, `content_hash`/`chunk_hash`, `parser_version`, `embedding_model_version` | next-gen.cloud, Oracle |
| Access | `tenant_id`, `security_level`, `allowed_roles` (**list**, không string) | reintech, samuelochoa |
| Domain | `language`, `locale`, `jurisdiction`, `doc_type`, `tags` | samuelochoa, stackai |

### Schema 4 bảng chuẩn (phù hợp stack PG-only)

```
documents (id, tenant_id, source_uri, deleted_at)
  └─ document_versions (content_sha256, file_sha256, extractor, completed_at)
       └─ chunks (version_id, chunker, ord, content_sha256, UNIQUE(version_id, chunker, ord))
            └─ chunk_embeddings (chunk_id, model, dim, embedding, PK(chunk_id, model))
```

- `tenant_id` denormalize xuống chunks/chunk_embeddings (RLS + filter không cần join)
- `extractor`/`chunker`/`model` trong UNIQUE constraint — upgrade parser → bump string, không thì bị bỏ im lặng
- content_sha256 cho phép mang ~90% embeddings qua re-index (chunk không đổi thì giữ)
- **KHÔNG dùng auto-increment làm chunk_id** — citation pointer chết khi rebuild. Dùng content-hash or stable doc-level ID.

### Tiếng Việt cụ thể
- Chunk theo **Điều/Khoản/Điểm** (không cắt theo độ dài cố định); metadata: **số hiệu, ngày ban hành, cơ quan, trạng thái hiệu lực** (claude.vn)
- Unicode NFC normalization + word segmentation (VnCoreNLP/Underthesea) cho BM25 (claude.vn)
- ViDRILL (VLSP 2025 peer-review): dual-level chunking — short ≤450 chars cho dense, long ≤2000 chars cho BGE-reranker-v2-m3 (aclanthology 2025.vlsp-1.17)
- Hybrid sparse+dense thắng đơn lẻ trên corpus pháp lý tiếng Việt (Springer chapter 978-3-032-14674-8_9)

---

## 2. Xử lý Dữ liệu Biến động (điểm khó nhất)

### 2.1. GIÁ — để NGOÀI vector index (đồng thuận mạnh)
> "Do not put fast-changing truth values (price, stock) in the vector index at all" (OST, Netguru, Okoone, 247 Labs, Algorithmine)

- Vector DB = **nghĩa** (tài liệu nào liên quan); **giá = live lookup lúc hội thoại** (cache-aside từ source of truth, TTL 1-6h)
- Cache key phải gồm `corpus_version` + campaign version — không thì cache phục vụ giá cũ
- **Freshness ≠ faithfulness**: faithful 0.89 vẫn có thể trích giá tuần trước — cần test case freshness riêng (Netguru, Okoone, 247 Labs)

### 2.2. Pháp lý — interval validity + filter-at-retrieval
```sql
WHERE effective_from <= :as_of
  AND (effective_to IS NULL OR effective_to > :as_of)
```
- Mặc định `as_of = now()`; câu hỏi lịch sử ("luật lúc đó") cho user date
- **Filter TRƯỚC khi LLM thấy context** — filter lúc hiển thị = rò rỉ (model đã đọc text cũ) (Ragnight, arXiv 2605.23497)
- Trích dẫn theo **điều/khoản + version**, không theo số trang (pagination đổi giữa version) (Ragnight)
- Component-level versioning: chỉ version các phần thay đổi, phần không đổi dùng lại (SAT-Graph RAG arXiv 2505.00039)
- **Cảnh báo đo được**: filter hiệu lực quá mạnh làm recall tụt (Recall@5 43.5% khi chỉ lấy in-force) — phải deliberate + eval, theo dõi metric "latest version recall" (LVR) (EurLex ablation)

### 2.3. Incremental update — content-hash + manifest
- **Content-hash (SHA-256) + manifest side table** `(doc_id, chunk_ids[], source_hash, model, indexed_at)` = nền tảng: phân loại new/changed/unchanged/deleted, chỉ re-chunk + re-embed phần đổi (Multigrid, TypeGraph, Oracle)
- **Thứ tự ghi**: ghi chunk MỚI trước, xóa chunk CŨ sau (reader tạm thấy trùng = vô hại; thấy cả hai biến mất = "câu trả lời không tồn tại"); manifest cập nhật CUỐI (Multigrid)
- **LightRAG update = delete-then-insert** (`adelete_by_doc_id` → re-insert), giữ LLM cache; không có "update overwrite" — re-upload cùng filename bị conflict (LightRAG issue #2219, discussion #1676)
- **Deletion là thao tác quyết định độ tin cậy**: "policy rút tháng 3 còn trong index tháng 8 sẽ bị retrieve và cite" (Multigrid); hard-delete source → orphan chunks; cần reconciliation (Oracle)

### 2.4. Đổi embedding model = full re-embed (bất biến)
- Vector 2 model khác nhau **không so sánh được** — "not less accurate, meaningless" (Multigrid, tianpan, dbi, NVIDIA)
- Migration chuẩn: shadow column `embedding_v2` + `CREATE INDEX CONCURRENTLY` + batch re-embed (1000/batch, checkpoint) + feature flag `USE_V2_EMBEDDINGS` + golden-set parity + giữ cũ ≥1 tuần rollback (Humza Tareen, tianpan)
- **Canary strings**: embed 20-50 chuỗi cố định lúc index, re-embed mẫu query, assert cosine ≥ 0.9999 — phát hiện provider đổi mapping âm thầm (tianpan)
- LightRAG: `rebuild_vdb` = path khôi phục (graph + chunks là source of truth, vector là derived artifact)

---

## 3. Schema Evolution & Scale (pgvector/PG)

### 3.1. JSONB vs columns — hybrid
- **Quy tắc**: "If you would ever want to index it, make it a column. If you would never query it on its own, it stays in JSONB" (Gold Lapel, Suparbase, unixy.io)
- Promote lên cột khi: WHERE phần lớn request / join từ bảng khác (JSONB không làm FK được) / ORDER BY / type correctness (timestamp, numeric) / aggregate (Gold Lapel, Suparbase, Codelit)
- Giữ JSONB khi: heterogeneous per-row, field không query riêng, sparse wide metadata
- `jsonb_path_ops` GIN > `jsonb_ops` cho containment ~90% trường hợp; GIN không giúp range query (cần expression btree index)
- **EAV = anti-pattern** — tránh tuyệt đối
- Generated columns `GENERATED ALWAYS AS (...) STORED` = cột query-able trên JSONB không dual-write drift

### 3.2. Evolution không downtime
- Additive-only: field mới vào JSONB; "WHERE đầu tiên" → promot lên cột, không bao giờ xóa/đổi tên cột
- `ADD COLUMN` với default constant = O(1) metadata-only (PG 11+); `CREATE INDEX CONCURRENTLY`; `SET lock_timeout='2s'` trước prod DDL
- Breaking change: Expand/Contract (dual-write → backfill batch 2-5k → swap → giữ cũ ≥1 tuần)
- Versioned metadata: `metadata_schema_version int` + JSONB (Stripe pattern nhẹ) — đủ vì ta chỉ thêm không xóa

### 3.3. pgvector
- `vector(1024)` — khớp aibox v4; **`embedding_model` trên mỗi chunk** = khuyến nghị được lặp nhiều nhất
- **HNSW > IVFFlat** cho incremental update: IVFFlat centroids đóng băng khi build → recall giảm dần khi insert tiếp; HNSW recall giữ qua insert (khớp chu kỳ 6 tháng). IVFFlat chỉ cho corpus tĩnh. Không build IVFFlat lúc schema migration (empty table = centroids rác)
- HNSW params m=16, ef_construction=64 ok; `hnsw.ef_search` (default 40) = dial live recall/latency, set per-query `SET LOCAL`
- Phân trang/HTAP: không cần index dưới ~10-50k rows (seq scan nhanh hơn)
- Hybrid = vector + tsvector GIN + **RRF** (k=60): `score = Σ 1/(60+rank)`; filter trong CẢ 2 CTE (vector AND lexical)

### 3.4. Multi-tenant / ACL
- `tenant_id`/`project_id` denormalize lên chunks; btree index trên `(project_id, status, effective_date)`
- **RLS là security boundary, không phải app filter**: `ENABLE ROW LEVEL SECURITY` + `FORCE` + `NOBYPASSRLS` + `set_config('app.tenant_id', $1, true)` per-transaction (kawshik.dev, multigrid RLS)
- Pre-filter quá selective (<1%) → planner xuống seq scan / "recall cliff" → fix: denormalize tenant lên chunk, pgvector ≥0.8 iterative scans, hoặc partition per tenant
- Ở quy mô <10k docs: `WHERE project_id = $1` + btree đơn giản là đủ

---

## 4. aibox + FastAPI (verify & patterns)

### 4.1. ⚠️ aibox — cần verify bằng test key (phát hiện mâu thuẫn)
- **3 sản phẩm tên "AI Box" khác nhau**: `api.ai-box.vn` (API gateway — đúng cái ta dùng), `ai-box.vn` (thiết bị loa AI — KHÔNG phải), `aibox.ai` (US SaaS — không liên quan)
- ✅ Base URL đúng: **`api.ai-box.vn/v1`** (giải quyết note mâu thuẫn trong CLAUDE.md)
- ✅ Chat completions: gateway OpenAI-compatible, deepseek-v4-flash đã được third-party monitor xác nhận (modelverify.ai)
- ⚠️ **Embedding/rerank qua aibox CHƯA có bằng chứng công khai** — site chỉ demo chat; `/v1/embeddings`, `/v1/reranks` (số nhiều, chuẩn Alibaba) cần test key thật trước khi khóa config
- ⚠️ Pricing: trang "bảng giá" không fetch được — unverified
- Nếu aibox chỉ chat: embedding/rerank phải từ Alibaba DashScope trực tiếp (text-embedding-v4 default 1024, $0.07-0.08/1M; qwen3-rerank `/v1/reranks` max 500 docs — gte-rerank deprecated 30/05/2026)

### 4.2. FastAPI patterns (đã verify)
- **SSE**: async generator + `StreamingResponse(media_type="text/event-stream")`; headers `X-Accel-Buffering: no` + `Cache-Control: no-cache`; KHÔNG gzip SSE; Nginx `proxy_buffering off; proxy_read_timeout 300s`; typed events (`rate_limit`, `sources`, `token`, `done`, `error`); **luôn emit `done` sau `error`** (finally); emit `sources` TRƯỚC khi generate (frontend render citation trong lúc stream); client dùng `fetch()+ReadableStream` (EventSource không POST được); backpressure `asyncio.Queue(maxsize=50)`; check `request.is_disconnected()` trong try/finally
- **Config**: 1 class Settings duy nhất (không per-env subclass), `env_file=(".env", f".env.{APP_ENV}")` — file sau thắng, env OS luôn thắng; `env_prefix="APP_"`, `extra="forbid"`, `SecretStr` cho key; `@lru_cache def get_settings()` làm dependency; fail fast khi thiếu required (app từ chối start)
- **API structure**: `POST /query` → `{answer, sources[], confidence, trace_id, latency_ms, token_usage}`; `POST /ingest` → 202 + job_id; `GET /status/{job_id}`; `GET /sources/{id}`; `GET /health` (liveness) ≠ `GET /ready` (check PG/vector)
- **Production**: `gunicorn -k uvicorn.workers.UvicornWorker` (hoặc package `uvicorn-worker` — module cũ deprecated); container = 1 uvicorn process; SSE endpoint `--timeout 0`; `lifespan` async context manager (không dùng @app.on_event); nginx SSL termination

---

## Key Takeaways → cập nhật schema (so với db/schema.sql hiện tại)

| # | Finding | Hành động |
|---|---|---|
| 1 | GIÁ ngoài vector index | Tách: `documents` (legal) vào LightRAG; **bảng `price_items` riêng** lấy live (không embed) |
| 2 | `embedding_model` trên chunk | Thêm cột vào document_chunks |
| 3 | `effective_from`/`effective_to` (half-open) | Thay `effective_date`/`expiry_date` — chuẩn interval + as-of query |
| 4 | Manifest + content-hash | Thêm bảng `document_manifest` (doc_id, chunk_ids[], source_hash, model) |
| 5 | HNSW không IVFFlat | Ghi chú index trong schema |
| 6 | Chunk theo Điều/Khoản + citation theo article | Section field quan trọng hơn page |
| 7 | RLS trên project_id | Thêm `project_id` denormalize lên chunks (MVP chưa cần RLS nhưng để sẵn) |
| 8 | aibox embedding/rerank chưa verify | **Bắt buộc test key trước khi chốt**: curl `/v1/models`, `/v1/embeddings`, `/v1/reranks` |

## Methodology
4 subagent song song (general-purpose, exa search + fetch), ~40 URL. Mỗi claim đa nguồn mới đánh "established"; single-source đánh dấu unverified. Nguồn chính: [multigrid](https://multigrid.ai/learn/rag-index-freshness), [TypeGraph](https://typegraph.ai/blog/incremental-re-indexing-rag-change-detection), [Oracle RAG drift](https://blogs.oracle.com/developers/how-to-detect-rag-index-drift-deleted-docs-stale-chunks-and-duplicate-embeddings), [tianpan embedding rotation](https://tianpan.co/blog/2026-04-23-embedding-rotation-database-migration-not-deploy), [EurLex ELI](https://eur-lex.europa.eu/eli-register/legis_schema_org.html), [arXiv 2605.23497 temporal legal](https://arxiv.org/html/2605.23497), [arXiv 2505.00039 SAT-Graph](https://arxiv.org/html/2505.00039), [LightRAG README](https://github.com/HKUDS/LightRAG/), [LightRAG #2219](https://github.com/HKUDS/LightRAG/issues/2219), [api.ai-box.vn](https://api.ai-box.vn/), [Alibaba rerank](https://docs.qwencloud.com/api-reference/rerank/openai-rerank), [FastAPI workers](https://fastapi.tiangolo.com/deployment/server-workers/), [SSE guide](https://www.server-sent-events.com/backend-stream-generation-connection-management/python-fastapi-sse-implementation-guide/)
