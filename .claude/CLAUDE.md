# rag-real-estate — RAG pháp lý bất động sản (MVP)

> Project memory — dự án RAG khác đọc để học theo. Kiến trúc đã quyết (2026-08-09, branch
> `feat/rag-real-estate-pilot`). Plan chi tiết: `.claude/plans/rag-real-estate-mvp.plan.md`.

## Nghiệp vụ

Chat hỗ trợ nhân viên công ty mua giới tìm nhanh tài liệu pháp lý nhà đất (văn bản pháp luật,
quy hoạch, hồ sơ dự án) để trả lời khách. **Dữ liệu thay đổi ~6 tháng/lần** → cần incremental
update, không rebuild.

## Cơ chế LightRAG (verify từ nghiên cứu 2026-08-09)

1 framework 3 trụ: **Graph-Based Text Indexing** (trích entity+relation, không chunk cô lập)
+ **Dual-Level Retrieval** (low-level entity / high-level themes) + **Incremental Update**
(merge node/edge, KHÔNG rebuild). 5 modes: local/global/hybrid/naive/mix → legal dùng **hybrid/mix**.
Storage: default in-memory file-persist = CHỈ dev; production **PG single-backend** → Neo4j/Memgraph
khi >10k docs. Token: retrieval overhead (keyword-gen + graph search) **<100 tokens**; context thực
gửi LLM giới hạn `max_entity_tokens=6000` / `max_relation_tokens=8000` / `max_total_tokens=30000` (default)
→ ≈10^4 tokens/lần query; khuyến nghị set `max_total_tokens` 8-12k cho legal.
vs GraphRAG: LightRAG incremental merge (paper: retrieval <100 vs 610k tokens; merge vs rebuild 14M
tokens; query 11.2s vs 23.6s; graphrag-lab 2026: 3.60/4.7s vs 3.10/0.9s faithfulness) — "2h/$22 vs
14h/$180" = estimate CHƯA có nguồn, chỉ tham khảo.

## Graph engine (đánh giá thư viện — quyết định CHƯA chốt, cần benchmark)

LightRAG core (`lightrag-hku`) mặc định dùng **NetworkX** cho graph ops (confidence: inferred từ
kiến thức nền, cần verify `pip show lightrag-hku` + grep khi implement). NetworkX = pure Python,
single-thread, memory-heavy trên graph lớn → **điểm yếu cố hữu** (đúng như user nêu).

| Thư viện | Runtime | Ưu | Nhược | Cho MVP legal? |
|---|---|---|---|---|
| **NetworkX** (default LightRAG) | pure Python | 0 cấu hình, đủ 10k-100k node | chậm, RAM nặng, không song song | POC/dev OK — **cần benchmark** |
| **python-igraph** | C core | nhanh 10-100x, bộ nhớ thấp | phải fork/adapt LightRAG storage | nếu benchmark chứng minh cần |
| **cuGraph** | GPU | nhanh nhất (graph lớn) | cần GPU, phức tạp ops | KHÔNG cho MVP |
| **Neo4j** | graph DB | query language, scale tốt | 1 infra nữa, ops nặng | khi >10k docs |
| **Memgraph** | in-memory graph DB | nhanh, Cypher | RAM, ops | khi >10k docs |

**Quyết định (đã verify 2026-08-09, subagent research)**: NetworkX chỉ cho dev/POC (in-memory,
single-writer). **Production dùng `PGTableGraphStorage`** (SQL trên PG, KHÔNG NetworkX, KHÔNG AGE) —
1 service, chạy được mọi PG managed (RDS/Supabase/Neon), nhanh hơn AGE ~20x (RPS 1431 vs 73, PR #3103).
Benchmark gate: nếu ingest thật >50k entity hoặc query latency >ngưỡng → chuyển iGraph/Neo4j.
Ghi `eval` của mục này vào task node khi implement.

## Quyết định kiến trúc (ADR-001)

| Trụ | Chọn | Ghi chú |
|---|---|---|
| RAG engine | **LightRAG 1.5.6 LOCK** (2026-08-06, Python ≥3.10) | Graph + vector; dual retrieval; incremental update; source tracking |
| Storage | **PostgreSQL single-backend** (PGKV/PGVector/**PGTableGraphStorage**/PGDocStatus) | 1 service; **PGTableGraphStorage** (plain PG tables, JSONB, KHÔNG Apache AGE — AGE chậm ~20x, không chạy nổi managed PG); migrate Neo4j khi >10k docs |
| Embedding | **aibox text-embedding-v4** dims **CHỐT 1024** (fallback local Qwen3-Embedding-0.6B — dims 1024, khớp) | **ĐÃ LOCK — đổi = re-embed toàn bộ**; ⚠️ verify base URL lúc implement (api-box.vn vs api.ai-box.vn) |
| Rerank | **aibox qwen3-rerank** `POST /v1/rerank` (Jina/Cohere-compatible; LightRAG `generic_rerank_api` response_format="standard") (fallback bge-reranker-v2-m3 — max 8192, recommend 1024) | verify 2026-08-09 |
| Extraction LLM | Claude Haiku / aibox qwen (rẻ) | |
| Query LLM | Model mạnh hơn (Sonnet / aibox qwen lớn) | |
| Frontend | **FastAPI + HTML/JS 1 trang** (REST+SSE); Flutter = phase 3 | API contract chuẩn ngay từ đầu |
| Cập nhật 6 tháng | Incremental insert + golden-set regression + pg_dump backup; metadata `effective_date`/`status` | |
| Anti-hallucination | Citation grounding + confidence 3-tier + human review high-stakes + audit log | Legal hallucinate ~1/6 |

## Quy tắc triển khai (bắt buộc)

1. **Embedding model LOCK** — cấu hình tập trung 1 chỗ (env), không hardcode; đổi model = re-embed toàn bộ.
2. **Citation bắt buộc** — mọi câu trả lời kèm source_ids; grounding: span trích dẫn phải nằm trong source chunk.
3. **Confidence 3-tier** — HIGH (≥2 nguồn, rerank ≥0.8, grounding pass) / MEDIUM / LOW; LOW + high-stakes keyword → human review.
4. **Golden set** (`eval/golden_set.json`, 20-30 câu) — chạy regression mỗi lần update 6 tháng và mỗi nâng cấp LightRAG.
5. **Backup trước update** — pg_dump + export graph; rollback có runbook.
6. **Secrets via env** — `AIBOX_API_KEY`, `AIBOX_BASE_URL`; CẤM ghi key vào file.
7. **Post-retrieval filter hiệu lực** — LightRAG KHÔNG filter theo metadata doc; build lớp filter
   `effective_date`/`status` riêng (registry doc → loại chunk hết hiệu lực trước khi đưa LLM), nếu
   không sẽ trả văn bản hết hiệu lực cho mua giới.
8. **Storage config CHỐT trước lần upload đầu** — pin `lightrag-hku==1.5.6` + `PGTableGraphStorage`
   + embedding dims 1024 trong config 1 nơi; đổi sau = re-index toàn bộ (không migration in-place).

## Env (giá trị qua biến môi trường, KHÔNG lưu file)

```
AIBOX_API_KEY=...        # embedding + rerank
AIBOX_BASE_URL=...       # /embeddings, /rerank
```

## Structure

```
ingest/    parser (MinerU/Docling) + extract + lightrag_init
eval/      golden_set.json + run_eval.py
api/       FastAPI /query + confidence + review_queue
web/       chat 1 trang
db/        audit.sql
scripts/   update_6mo.sh (backup → incremental → regression)
```

## Lessons đã học (từ vault graph-orchestrator)

- RAG legal: LightRAG 84.8% vs NaiveRAG 15-40% (benchmark 2025-2026) → graph-aware thắng cho tài liệu liên chéo văn bản.
- Đổi embedding model = phá toàn bộ vector cũ → lock model từ đầu, wrapper tập trung.
- Legal LLM hallucinate ~1/6 → citation + grounding + confidence + human review là bắt buộc, không phải optional.

## Domain insight — "đất cầm" (research 2026-08-09, `docs/research/legal-domain-research.md`)

**"Đất cầm" = 2 khái niệm pháp lý ĐỐI LẬP, chatbot phải phân biệt + cảnh báo rủi ro, không gộp chung:**
1. **Thế chấp ngân hàng** — hợp pháp, quy trình chuẩn (thỏa thuận 3 bên → giải chấp → công chứng → sang tên).
2. **Cầm cố QSDĐ / "cố đất"** — KHÔNG được Luật Đất đai 2024 ghi nhận (Điều 27 không liệt kê),
   tòa án tuyên vô hiệu theo Điều 123 BLDS 2015 → rủi ro cao nhất, đòi human review.

**Taxonomy 4 nhóm**: T1 thế chấp ngân hàng · T2 cầm cố tư nhân & giấy tay · T3 hồ sơ dự án & pháp lý
thửa đất · T4 văn bản pháp luật nền. Metadata bắt buộc: `effective_date`/`status` (Luật Đất đai 2024
hiệu lực 01/01/2025, Luật KDBĐS 2023 từ 01/08/2024 → văn bản cũ đánh `expired`). Golden set seed
30 câu tại `docs/research/legal-domain-research.md`. High-stakes keywords: cầm cố, thế chấp, chuyển
nhượng, công chứng, quy hoạch, thuế, diện tích, sổ đỏ, giải chấp, tranh chấp, ủy quyền, kê biên, hiệu lực.

## Basesource (ĐÃ DỰNG — 2026-08-10, verify: FE build PASS · Python import-smoke PASS · eval dry 8/8 · injection 100%)

> Basesource viết theo `rag-real-estate-final.plan.md` §16.1. Cấu trúc: `api/` (FastAPI 8-step
> pipeline) · `ingest/` (config+lightrag_init+parser+fact_extract+placeholder+load) · `db/`
> (schema.sql v2 + audit.sql + seed/) · `apps/web` + `packages/contracts` + `packages/ui`
> (FE monorepo Next.js 15 + antd v5) · `eval/` + `scripts/` + `prompts/`.

**Quyết định lệch/đáng biết (chi tiết: memory `ragre-basesource-open-items`):**
1. **`api/workflow.py` = asyncio orchestrator** (fallback plan §4.0) — LlamaIndex Workflows chưa
   bọc vì spike chưa chạy (không Python lúc dựng). Cấu trúc sẵn để bọc sau.
2. **L1 guard rule-based đạt 100%** trên `eval/injection_test_vn.json` (10 injection + 10 benign).
3. **FE = Next.js** (thay plan §16.5 vanilla web/) — user chốt; proxy `/api/*` → FastAPI :8000.
4. **Python 3.13.2 at `/d/miniconda3/python.exe`**; `.venv` đã tạo (fastapi/asyncpg/pydantic/openai/
   httpx/sqlglot). `pip install -r requirements.txt` + 4 spike plan §10 CHƯA chạy (lightrag-hku,
   llama-index-core chưa cài — verify wheel 3.13 trước).
5. **Schema fix:** `GRANT ro_query TO ragre` + `GRANT SET ON ROLE ro_query` trong db/schema.sql
   (thiếu → `SET LOCAL ROLE ro_query` fail).

**Chạy dev:** `docker compose up -d` → `psql -f db/schema.sql` + `db/audit.sql` + `db/seed/*.sql`
→ `.venv/Scripts/python -m uvicorn api.main:app --port 8000` → `npm run dev:web` (:3000).

## Chuẩn format & code quality (bắt buộc — 2026-08-11)

1. **Format chuẩn toàn team** (tránh conflict khi save): `.editorconfig` (root: LF, final newline, indent py=4 / ts-js-css=2) + `.prettierrc.json` (FE: semi, printWidth 100) + `pyproject.toml` `[tool.ruff]` (BE: line-length 100, select E/F/I/B/UP). **Mọi file mới phải kết thúc bằng newline, không trailing whitespace.**
2. **Import path FE**: dùng alias `@/` (tsconfig `paths`), CẤM `../..` dài — `@/lib/api`, `@/components/...`.
3. **.gitignore**: node_modules/ `**/node_modules/`, `.venv/`, `__pycache__/`, `*.py[cod]`, `.next/`, `dist/`, `build/`, `.env.*` (giữ `.env.example`), `.claude/` local state, `_bmad/`, `.turbo/`, `*.log`, `*.tsbuildinfo`. Thư mục install KHÔNG commit.
4. **Comment Google-style**: tiếng Anh, RẤT ít, chỉ WHY; docstring 1-3 dòng public API; CẤM banner `# ----` + comment tiếng Việt dài. Naming tiếng Anh tường minh (lesson `rag-comment-naming-google-style`).
5. **Push PR**: PHẢI build thật PASS trước khi push — BE `python -m compileall -q api ingest eval` + import-smoke, FE `npm run build --workspace=@rag-ragre/web` + `npm run typecheck`. Không push khi mới "verify test syntax".
6. **External services (LLM/rerank/embedding)**: qua Ports & Adapters (`api/ports/` Protocol + `api/adapters/` + `api/dependencies.py` DI) — đổi provider chỉ sửa 1 adapter (lesson `rag-fastapi-ports-adapters-ddd`).
