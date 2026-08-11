# Plan: RAG Bất động sản pháp lý — MVP (feat/rag-real-estate-pilot)

> Pilot task #1 cho skill graph-orchestrator v2. Phạm vi task này: **research + architecture + plan**
> (KHÔNG implement code — project mới, trống). Implement là task riêng sau khi plan approve.
> Branch: `feat/rag-real-estate-pilot` | Scope: POC → MVP cấp vốn.

## Yêu cầu nghiệp vụ (restate)

Công ty mua giới cần chat hỗ trợ nhân viên tìm nhanh tài liệu pháp lý nhà đất
(văn bản pháp luật, quy hoạch, hồ sơ dự án) để trả lời khách. Dữ liệu thay đổi ~6 tháng/lần.
Ưu tiên: **LightRAG**, MVP cấp vốn nhanh, dễ mở rộng.

## Cơ chế LightRAG (chi tiết — verify từ nghiên cứu, không bịa)

**1 framework, 3 trụ:**
1. **Graph-Based Text Indexing**: không cắt chunk cô lập — đọc văn bản, trích entity
   (tên, địa điểm, khái niệm) + relation → xây graph + vector.
2. **Dual-Level Retrieval**: low-level (entity/relation cụ thể) + high-level (themes/topics).
3. **Incremental Update**: doc mới → merge node/edge vào graph cũ, KHÔNG rebuild.

**5 retrieval modes**: `local` / `global` / `hybrid` (2 tầng) / `naive` (dense thuần = RAG cổ điển)
/ `mix` (tất cả + keyword). → **Legal chọn `hybrid` hoặc `mix`**.

**Graph storage cho MVP**:
- Default LightRAG = in-memory + file persist → **CHỈ dev/debug, KHÔNG production**.
- Production: **PG single-backend** (PGKVStorage + PGVectorStorage + **PGTableGraphStorage** —
  graph lưu plain PG tables JSONB, KHÔNG Apache AGE) → Neo4j/**Memgraph** chuyên graph khi >10k docs.
- Token: retrieval overhead (keyword-gen + graph search) **<100 tokens**; context LLM giới hạn
  `max_total_tokens` (default 30k, khuyến nghị 8-12k cho legal).

**LightRAG vs GraphRAG (lý do chọn)**: GraphRAG KHÔNG incremental — mỗi update = full reindex
(vd rebuild 14M tokens); LightRAG merge node/edge (retrieval <100 vs 610k tokens; query 11.2s vs
23.6s — paper EMNLP 2025). → Khớp chu kỳ 6 tháng. ("2h/$22 vs 14h/$180" = estimate chưa có nguồn.)

**So vs RAG cổ điển (ai-nlp-toolkit blueprint)**: chunk→embed→storage→hybrid RF→rerank→cite.
LightRAG thay bước chunk-isolation bằng graph + dual retrieval, GIỮ discipline: cite bắt buộc,
guardrail no-evidence fallback, chunk metadata (source/title/section/timestamp).

## Quyết định kiến trúc (architect agent — 2026-08-09)

| Quyết định | Lựa chọn | Lý do chính |
|---|---|---|
| Hướng RAG | **LightRAG** (pin version) | Legal 84.8% vs NaiveRAG 15-40%; incremental update khớp chu kỳ 6 tháng; source tracking sẵn |
| Storage MVP | **PostgreSQL single-backend** (PGKV/PGVector/**PGTableGraphStorage**/PGDocStatus) | 1 service, pg_dump dễ, chạy được managed PG; lộ trình Neo4j khi >10k docs |
| Embedding/Rerank | **aibox** text-embedding-v4 + qwen3-rerank (đã verify); fallback local (Qwen3-Embedding-0.6B, bge-reranker-v2-m3). **Lock embedding model ngay** | Không thêm infra; đổi embedding = re-embed toàn bộ |
| Extraction LLM | Claude Haiku / aibox qwen (rẻ) | Chạy khối lượng lớn |
| Query LLM | Model mạnh hơn (Sonnet / aibox qwen lớn) | Chất lượng trả lời |
| Frontend MVP | **FastAPI + HTML/JS 1 trang** (REST + SSE); Flutter app = phase 3 | Backend tái dùng; Streamlit yếu auth/audit/streaming |
| Cập nhật 6 tháng | Incremental insert + golden-set regression + pg_dump backup trước update; metadata `effective_date`/`status` filter theo hiệu lực | Tránh trả version hết hiệu lực |
| Anti-hallucination | **Bắt buộc**: citation grounding + confidence 3-tier + human review high-stakes + audit log | Legal hallucinate ~1/6; fake citation nguy hiểm nhất |
| Document roles & lifecycle | **State machine** `draft→review→approved→published→deprecated→deleted`; chỉ `published` vào index; deleted = cascade delete; **RBAC 7 vai, uploader ≠ approver (SSD)** | "Roles quản lý tài liệu" đang thiếu — AD-3, AD-5 |
| Access control | **PG RLS** trên chunk table: `FORCE RLS` + `NOBYPASSRLS` + identity `SET LOCAL` + fail-closed; ACL metadata dán lên từng chunk lúc ingest | LLM không được thấy doc không được phép — AD-4 |
| Guardrails injection | **4 lớp**: Llama Prompt Guard 2 (22M) screen input+chunks · instruction hierarchy + delimiters · chunk limits + hash/provenance · output grounding; CẤM concat retrieved vào system prompt | Indirect injection = rủi ro #1 RAG — AD-6 |
| Eval ops | **Golden set version cùng corpus** `golden_set_v{N}.json` + re-baseline sau update 6 tháng; PR gate = faithfulness+answer-relevancy subset, nightly = full 4 metric | Eval invalidation paradox — AD-8 |
| Deploy MVP | **Viettel Cloud VPS** (2-4vCPU/4GB, ~235-315k/tháng) tự quản PG cùng box tại DC 02 Quang Trung ĐN; defer managed vDBS; quote vendor trước khi chốt | "Giá rẻ thôi, Viettel chát quá" → chọn VPS rẻ thay vì premium — AD-9 |

## Gap vs architecture spine (2026-08-10)

> Kết quả `bmad-architecture` (Fast path) — spine đầy đủ tại
> `docs/architecture/architecture-rag-real-estate-2026-08-10/ARCHITECTURE-SPINE.md` (AD-1..AD-10).
> Research nguồn: `docs/research/guardrails-roles-mlops-research.md`.

| Khu vực | Plan cũ | Spine bổ sung | Trạng thái |
|---|---|---|---|
| Storage | ✅ PG single-backend | AD-1 (giữ nguyên) | Không gap |
| Embedding | ✅ aibox v4 dims 1024 LOCK | AD-2 (giữ nguyên) | Không gap |
| Anti-hallucination | ✅ citation + confidence 3-tier + audit log | AD-6 L4 + AD-10 | Giữ, mở rộng |
| **Roles quản lý tài liệu** | 🔴 **KHÔNG có** | AD-3 state machine + AD-5 RBAC 7 vai + SSD | **Gap lớn nhất — đóng** |
| **Access control** | 🔴 Chỉ có post-retrieval filter hiệu lực | AD-4 PG RLS retrieval-time ACL (fail-closed) | **Gap lớn — đóng** |
| **Chống prompt injection** | 🔴 KHÔNG có | AD-6 4 lớp (Prompt Guard 2 + instruction hierarchy + hash/provenance + grounding) | **Gap lớn — đóng** |
| Incremental update | ⚠️ "Incremental insert" chung chung | AD-7 chunk ID ổn định `doc_id:chunk_index` + content-hash (chỉ re-embed chunk đổi) | Gap — đóng |
| Eval | ⚠️ Golden-set regression mỗi update | AD-8 version golden set cùng corpus + re-baseline (eval invalidation paradox) + CI split suite | Gap — đóng |
| **Deploy/provider** | 🔴 **KHÔNG có quyết định** | AD-9 Viettel VPS tự quản PG rẻ (~235-315k) tại DC Đà Nẵng; defer vDBS | **Gap lớn — đóng** |
| Env/audit | ⚠️ Secrets via env | AD-10 dev/staging/prod tách biệt + audit replayable | Gap — đóng |
| AI-Engineering rules | 🔴 Ngoài plan | → `.claude/rules/` của project (hooks hard-block, plan-first, test trước merge) | Việc riêng, không trong plan code |

**Impact lên pha triển khai** (bổ sung vào các phase hiện có):
- **Week 1-2**: thêm `db/schema.sql` — bảng `documents` (state machine + metadata contract) + RLS policies trên chunk tables; ingest gắn ACL metadata + content-hash.
- **Week 3-4**: thêm `api/guard.py` (Prompt Guard 2 screen) + prompt-construction theo instruction hierarchy; RLS identity qua `SET LOCAL`.
- **Week 5-6**: `eval/golden_set_v1.json` + versioning; CI gate (PR subset / nightly full); deploy script lên Viettel VPS (Docker Compose, pg_dump backup).

## Pha triển khai (implement — task RIÊNG sau approve)

### Week 1-2: Pipeline ingest
- `ingest/parser.py` — MinerU/Docling parse PDF/Word → semantic chunk giữ ranh giới điều/khoản
- `ingest/extract.py` — extraction LLM (Haiku/aibox qwen) → entity/relation cho LightRAG
- `ingest/lightrag_init.py` — LightRAG với PGStorage (KV/Vector/Graph/DocStatus)
- `eval/golden_set.json` — 20-30 câu hỏi mẫu + đáp án + script eval (accuracy, citation correctness)
- Verify: `pip install lightrag-hku` + ingest 50-100 văn bản POC → `python eval/run_eval.py` ra baseline

### Week 3-4: Query pipeline + chat web
- `api/main.py` — FastAPI: `POST /query` (hybrid + rerank + citation), `GET /sources/:id`, SSE stream
- `api/confidence.py` — confidence 3-tier: HIGH (≥2 nguồn, rerank ≥0.8, grounding pass) / MEDIUM / LOW
- `web/index.html` — chat 1 trang + hiển thị citation + confidence badge
- `api/review_queue.py` — LOW hoặc high-stakes keyword → bắt buộc human review
- `db/audit.sql` — audit log: query, chunk IDs, rerank score, source_ids, confidence, verdict
- Verify: query 20 câu golden set → accuracy tăng vs baseline; citation trỏ đúng chunk

### Week 5-6: Cập nhật 6 tháng + hardening
- `scripts/update_6mo.sh` — backup (pg_dump + export graph) → incremental insert → golden-set regression → publish
- Metadata `effective_date`/`status` filter khi query
- Demo cấp vốn: benchmark trước/sau LightRAG trên golden set

## Lệnh verify cho từng bước (đầy đủ khi implement)

| Bước | File | Verify |
|---|---|---|
| Ingest POC | `ingest/*.py` | `python -c "from lightrag import LightRAG; print(LightRAG)"`; ingest 50 docs OK |
| Golden set | `eval/golden_set.json` | `python eval/run_eval.py` chạy được, in accuracy |
| Query API | `api/main.py` | `curl -X POST localhost:8000/query -d '{"q":"quy hoạch dự án X"}'` → JSON có answer + sources |
| Confidence | `api/confidence.py` | unit test 3 tier: ≥2 nguồn+rerank≥0.8 → HIGH |
| Update 6 tháng | `scripts/update_6mo.sh` | dry-run trên dump giả → regression pass |

## Non-goals (task này / phase này)

- KHÔNG implement code trong task hiện tại (pilot chỉ research + architecture + plan)
- KHÔNG chọn Neo4j/Qdrant ở MVP (khi >10k docs)
- KHÔNG làm Flutter app ở MVP (phase 3)
- KHÔNG fine-tune embedding (lock model có sẵn)

## Success signal

1. Plan này được user review + approve (qua plan-canvas).
2. Architect đã quyết định đủ 6 trụ (RAG/storage/embedding/LLM/frontend/anti-hallu).
3. Memory đã lưu vào `D:/rag-real-estate/.claude/CLAUDE.md` — dự án RAG khác đọc được (yêu cầu #5).
4. RECORD xong vào vault: task node + lessons + daily + MOC + eval.
