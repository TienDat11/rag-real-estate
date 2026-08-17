You are a backend performance engineer working in the repo D:\rag-real-estate (Windows host; use the pwsh tool; Python venv is at D:\rag-real-estate\.venv\Scripts\python.exe).

FIRST ACTION: load these skills via the skill tool (exact names): "benchmark", "react-performance", "diagnosing-bugs", "benchmark-optimization-loop". Follow their methodology (esp. diagnosing-bugs feedback loop phases and benchmark-optimization-loop baseline/variant-table discipline).

## The bug (user-reported, live log)
POST /query with the Vietnamese compound question:
"Căn CH-10 có nhìn ra biển được không? Và hiện tại có căn nào nhìn ra biển. Và những tiện ích tôi mua căn CH10 hả bạn?"
is far too slow and the user saw timeouts. Their real uvicorn log shows (twice):
  rewrite attempt 1 failed: LLM complete timeout (20.0s) model=deepseek-v4-flash
and RAG leg logs showing heavy work: "Query nodes: giá, CH-10 (top_k:40, cosine:0.2)", "Local query: 40 entites, 125 relations", "Final context: 40 entities, 125 relations, 19 chunks".
Also logged: "QueryParam full kwargs fail (... 'addon_params') — fallback minimal" (LightRAG legacy kwargs warning, benign-ish) and LightRAG internal "Role LLM Configuration ... extract/query: None/None, host=None".

## Environment constraint (critical — read carefully)
This agent environment has NO live PostgreSQL and NO reachable LLM API. You CANNOT reproduce the timeout by hitting real services, and eval must stay offline. Work like this:
- Diagnose by reading code (api/rewrite.py, api/constants.py, api/workflow.py, api/rag_leg.py, api/main.py, api/config.py).
- Build/run offline tests that mock the LLM/pool (existing pattern: tests monkeypatch api.sql_leg._fetch_estimates; there is NO pytest-asyncio in this repo — async tests use asyncio.run(go()) inside sync test functions). Inspect tests/ to match conventions.
- Measure what is measurable offline (e.g., pure-function throughput with a stubbed LLM, pipeline cold-path timing with mocks) to build a baseline table. Do NOT invent wall-clock numbers for real LLM calls; where you cannot measure without live infra, say so explicitly and print the commands the user must run live (they run uvicorn + docker compose postgres + real LLM env vars).
- Never fabricate measurements.

## Known facts from code inspection
- api/constants.py: LLM_CALL_TIMEOUT_S = 20.0 ("per-operation LLM call budget (rewrite / nl2sql)"); DEFAULT_LLM_TIMEOUT_S = 30.0; workflow timeout default 180.0s (api/workflow.py line 131).
- api/rewrite.py around lines 446-456: rewrite makes 2 attempts ([messages, messages + [JSON-invalid correction]]), each calling llm.complete(..., timeout=LLM_CALL_TIMEOUT_S). So worst case the rewrite spends 2 x 20s = 40s before giving up and falling back. The user's log shows the first attempt timing out at exactly 20s. This is the prime suspect for the perceived hang.
- api/workflow.py: STEP_TIMEOUTS dict gates guard (line 185) and rewrite (lines 207-209) via asyncio.wait_for. Pipeline emits SSE via self._emit(event, data) with existing events PLACES/SOURCES/FACTS/TOKEN (constants). The workflow timeout is 180s.
- RAG leg top_k=40 with entity/relation token budgets (DEFAULT_MAX_ENTITY_TOKENS=2000, DEFAULT_MAX_RELATION_TOKENS=2000, DEFAULT_MAX_TOTAL_TOKENS=6000); the compound 3-part question widens the query.

## Scope of this agent (BE only)
Fix the slowness/timeout with a diagnosed, benchmarked change. Ideas to investigate (your call after measuring/reading, with a variant table):
1. Rewrite timeout handling: is 2x20s retry acceptable? Should the timeout be lowered for rewrite, attempts be bounded so a TIMEOUT on attempt 1 does not burn a second 20s attempt (a timeout is not "invalid JSON"; only a JSON parse failure should trigger the correction retry), or should timeout mid-flight fall back to a rule-based route immediately (structured_path default) instead of blocking 40s?
2. STEP_TIMEOUTS sizing vs LLM_CALL_TIMEOUT_S consistency.
3. RAG heaviness on compound queries: cap/limit what gets widened, check top_k and budgets, and whether the compound question causes an oversized graph query.
4. Any other hotspot you find via the diagnosing-bugs loop.

IMPORTANT: keep behavior correct — routing must still produce the same structured_path semantics (spec/nl2sql/affordability/pricing/none, pricing force/demote logic in api/rewrite.py must be untouched semantically), guards must still fire, audit still written. Do NOT weaken correctness for speed. Do not silence errors by catch-and-ignore; prefer bounded retries/fallback paths that are explicit and logged.

## Second deliverable: SSE progress events (BE side only)
Add a new SSE event named "progress" emitted by the workflow at each pipeline step so the frontend can show the customer what is happening. Requirements:
- Add SSE_EVENT_PROGRESS = "progress" to api/constants.py (do NOT change existing event names/order).
- Emit from api/workflow.py steps via self._emit(SSE_EVENT_PROGRESS, {...}) with ONLY raw step keys — the friendly Vietnamese display text belongs to the frontend (another agent owns apps/web). Safe payload shape: {"step": "guard" | "rewrite" | "rag" | "sql" | "geo" | "rerank" | "merge" | "generate"}, plus optional {"detail": ...} only if it contains NO ids, NO internal names, NO file paths, NO token counts, NO model names. When unsure, omit detail — the no-leak rule wins.
- Emit before the first await of each step so the UI can show progress while the step runs; emit a final {"step": "done"} when the pipeline finishes (or on error, emit {"step": "error"} then done) — coordinate with the existing PLACES/SOURCES/FACTS/TOKEN order; keep that order unchanged.
- Update tests: existing SSE-related tests must keep passing; add a test asserting the progress event sequence for a mocked run.
- packages/contracts has API_SSE_EVENTS — do NOT edit packages/ (another surface; the web agent will mirror the new event name). Keep BE self-contained otherwise.

## Deliverables from this agent
1. Root-cause write-up (what actually slows the query, evidence from code + offline runs).
2. Baseline + after variant table (target: rewrite worst-case latency drops from ~40s toward a bounded budget; overall query latency reduced; no correctness regression).
3. Code changes + regression tests (e.g. a test that when llm.complete raises a timeout, the rewrite falls back WITHOUT a second LLM call if that is the chosen design — plus any tests proving bounded latency).
4. Exact commands the user runs live to measure on their machine (uvicorn startup, docker compose exec psql for /ready, curl POST /query with Accept: text/event-stream, and what numbers to compare).
5. Export your final report as a markdown file at D:\rag-real-estate\_tmp_be_perf_report.md (note in the report that it should be deleted before commit).

Constraints: commentary in code must be English and explain WHY, not describe what. Ruff line length 100. Do not touch apps/web/ or prompts/. Do not break the uncommitted story-3.3 pricing work in api/ (price tiers, structured_path "pricing" routing, v_unit_estimates views). Run the offline suite: D:\rag-real-estate\.venv\Scripts\python.exe -m pytest -q (expect roughly 172+ passing) and ruff: .venv\Scripts\python.exe -m ruff check api tests (note: a baseline of pre-existing violations in api/adapters, api/rewrite.py, api/sql_leg.py, eval/run_eval.py is known — you must not ADD new violations; report any you fix).