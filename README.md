# rag-real-estate — RAG legal real-estate search (basesource)

Chat bot hỗ trợ nhân viên môi giới tra cứu nhanh tài liệu pháp lý nhà đất (văn bản pháp luật,
quy hoạch, hồ sơ dự án, chính sách giá bán) để trả lời khách hàng.

## Status (basesource)

- **Verified:** BE `python -m compileall -q api ingest eval` + import-smoke PASS · FE `next build`
  + `typecheck` PASS · eval offline dry-run (harness self-test only — chưa gọi LLM thật).
- **NOT runtime-verified:** schema/seed SQL chưa từng chạy trên DB thật; chưa có lần gọi
  LLM/rerank/embedding trực tiếp nào; chưa có `.env` secrets (chỉ có `.env.example`).
- **Blocked on:** docker + PostgreSQL + API keys trước khi chạy runtime được.
- **Run bên dưới là đường chạy dự kiến (intended path), không phải một lần chạy đã ghi nhận
  (recorded run).**

## Architecture

### Backend — FastAPI 8-step query pipeline
```
POST /query  →  input guard → rewrite/route → (RAG leg ∥ SQL leg) → rerank → merge
              → generate (SSE stream) → output guard → audit
```
- **RAG leg**: LightRAG graph + vector retrieval (PostgreSQL single-backend)
- **SQL leg**: structured facts (giá, chính sách vay) — spec-builder giới hạn field/op, chạy
  với RLS role `ro_query`, LLM không tự tính toán
- **External services qua Ports & Adapters**: `api/ports/` (Protocol) + `api/adapters/`
  (OpenAI-compatible LLM, HTTP rerank, no-op) — đổi provider chỉ đổi 1 adapter
- **Anti-hallucination**: citation + confidence 3-tier + output guard + audit log

### Database — PostgreSQL (schema v2)
- `documents` / `document_chunks` — registry tài liệu + chunk (metadata `effective_from/to`)
- `facts` / `fact_subjects` — structured facts, interval validity, NUMERIC kỷ luật
- `v_unit_offers` — derived view (affordability), `security_invoker` qua RLS
- Query chạy `SET LOCAL ROLE ro_query` trong transaction

### Frontend — Next.js 15 (monorepo, npm workspaces)
- Workspace names: `@rag-ragre/web` · `@rag-ragre/contracts` · `@rag-ragre/ui`
- `apps/web` — chat UI: SSE streaming (sources → facts → token → done), citation, confidence,
  review banner (Ant Design v5 + Tailwind)
- `packages/contracts` — TypeScript API contract types + constants (single source)
- `packages/ui` — presentational components

### Eval
- Golden set 32 câu (faithfulness / numeric-exact / latency) + prompt-injection test VN (20 câu)

## Run

```bash
# 1. Dev DB — áp schema + seed theo thứ tự (xem db/seed/README.md)
#    KHÔNG cần cài psql trên máy: gọi psql BÊN TRONG container postgres.
#    Chạy từ thư mục repo (nơi có docker-compose.yml).
docker compose up -d
PSQL="docker compose exec -T postgres psql -U ragre -d ragre -v ON_ERROR_STOP=1"
$PSQL < db/schema.sql
$PSQL < db/audit.sql
$PSQL < db/camellia_estimate.sql       # package camellia + view v_unit_estimates
$PSQL < db/seed/camellia_rumor.sql     # 6 unit types (attrs.price_tiers) + 24 range facts
$PSQL < db/seed/legal_docs.sql && $PSQL < db/seed/price_campaigns.sql \
  && $PSQL < db/seed/policy_vay.sql    # optional — policy đã có trong price_campaigns.sql
$PSQL < scripts/verify_ingest.sql      # verify seed (mọi count phải = 0/OK)

# 2. Backend (copy .env.example → .env, điền secret)
.venv/Scripts/python -m uvicorn api.main:app --port 8000

# 3. Frontend
npm run dev:web   # → http://localhost:3000
```

> **Lưu ý seed 3.3 (pricing tiered leg):** `db/camellia_estimate.sql` PHẢI chạy trước
> `db/seed/camellia_rumor.sql` (camellia_rumor tạo price_tiers attrs cho 6 loại căn +
> 24 fact range — view `v_unit_estimates` cần có sẵn từ estimate file). Giá 1m² theo
> tầng và theo mã căn đều đọc từ DB này, không phải LLM tính (ADR-0002 D2/D6).

## Quality gates (bắt buộc trước khi push PR)

- BE: `python -m compileall -q api ingest eval` + import-smoke PASS
- FE: `npm run build --workspace=@rag-ragre/web` + `npm run typecheck` PASS
- Format: `.editorconfig` (LF, final newline) · `.prettierrc.json` (TS/JS) · `pyproject.toml` (ruff: line-length 100)
- PR title: `[Status] <mô tả rõ ràng>` theo convention (xem CLAUDE.md)
