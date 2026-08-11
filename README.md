# rag-real-estate — RAG pháp lý + giá + chính sách vay bất động sản

> Chatbot nội bộ cho công ty mua giới: trả lời nhanh câu hỏi pháp lý nhà đất, giá căn hộ,
> chính sách vay ngân hàng — với citation, confidence 3-tier, human review cho case high-stakes.
>
> Plan chi tiết: `.claude/plans/rag-real-estate-final.plan.md` (APPROVED 2026-08-10).

## Kiến trúc 1 dòng

*facts (giá/policy/diện tích) NGOÀI vector index — bảng SQL interval-validity + VIEW `v_unit_offers`;
chunk mang placeholder `⟦FACT:key@subject⟧`; query = pipeline 8 step: guard → rewrite+route →
(chân RAG LightRAG hybrid ∥ chân SQL spec/NL2SQL) → hydrate+filter → rerank app-side → generate
→ L4 output guard → audit + SSE.*

## Tech stack

| Lớp | Chọn | Ghi chú |
|---|---|---|
| RAG engine | **LightRAG 1.5.6** (graph + vector, incremental) | `only_need_context`, chunking passthrough |
| Orchestration | **LlamaIndex 0.14.23 Workflows** (spike-verify) | fallback asyncio trong step — không block MVP |
| Storage | **PostgreSQL 16.6+ pgvector** single-backend | facts + registry + LightRAG PG storages |
| Embedding | **text-embedding-v4 dims 1024 LOCK** | đổi model = re-embed toàn bộ |
| Rerank | **qwen3-rerank app-side** | nguồn score DUY NHẤT cho confidence |
| Backend | **FastAPI** (SSE streaming) | clean architecture, typed contracts |
| Frontend | **Next.js 15 App Router + Ant Design v5 + Tailwind** | monorepo `apps/web` + `packages/*` |
| Eval | golden set + run_eval (faithfulness, numeric exact-match, P50/P95) | |

## Cấu trúc repo

```
rag-real-estate/
  apps/web/            # Next.js chat app (SSE streaming, facts table, confidence badge)
  packages/contracts/  # Shared TS types — API contract (mirror Pydantic §16.2)
  packages/ui/         # Design system (ThemeProvider, ConfidenceBadge, FactsTable, ...)
  api/                 # FastAPI: workflow 8 step, guard, rewrite, rag/sql legs, guard_output, audit
  ingest/              # config, lightrag_init, parser (Docling), fact_extract, placeholder, load
  db/                  # schema.sql v2, audit.sql, seed/
  eval/                # golden_set_v1.json, injection_test_vn.json, run_eval.py
  scripts/             # verify_ingest.sql, update_price.sh, update_6mo.sh
  prompts/             # entity_type/legal_vn.yml, rewrite_fewshot.md, system_policy.md
```

## Chạy nhanh (dev)

```bash
# 1. DB
docker compose up -d            # PG 16.6 + pgvector trên :5432
psql -U ragre -d ragre -f db/schema.sql
psql -U ragre -d ragre -f db/audit.sql
psql -U ragre -d ragre -f db/seed/price_campaigns.sql   # seed bảng giá mẫu

# 2. Backend (Python >= 3.10)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # điền API key thật
uvicorn api.main:app --reload --port 8000

# 3. Frontend (Node >= 20)
npm install                      # workspaces: apps/web + packages/*
npm run dev:web                  # http://localhost:3000 (proxy /api -> :8000)

# 4. Ingest + eval
python -m ingest.load --doc db/seed/data/legal/A.doc.json
python eval/run_eval.py --subset
```

## API contract

`POST /query` (REST hoặc SSE với `Accept: text/event-stream`):
sources → facts → token* → done (kèm answer, confidence, requires_review, trace_id, latency_ms).
Chi tiết: plan §16.2-16.4 · types: `packages/contracts/src/index.ts`.

## Quy tắc bất biến

1. Facts NGOÀI vector index — SQL là nguồn số liệu DUY NHẤT, generation KHÔNG tự tính.
2. Structured TRƯỚC vector. Filter hiệu lực TRƯỚC khi LLM thấy context.
3. Citation bắt buộc + confidence 3-tier + HIGH-stakes → human review.
4. SQL an toàn: closed-set validate (R1) + sqlglot AST guard (R2); role `ro_query` read-only.
5. Secrets chỉ qua env (`cp .env.example .env`); CẤM commit key.
