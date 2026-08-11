# Review: Tech-Verify Lens — ARCHITECTURE-SPINE.md

- **File reviewed:** `docs/architecture/architecture-rag-real-estate-2026-08-10/ARCHITECTURE-SPINE.md`
- **Lens:** every committed decision web-researched / reality-checked, not asserted from training data — current versions, technologies still exist and fit, live defaults of any starter.
- **Source of record:** `docs/research/guardrails-roles-mlops-research.md` (web-verified 2026-08-10). Cross-checked against `docs/research/library-research.md` (2026-08-09) and `docs/research/storage-pipeline-research.md` (2026-08-09), plus `.claude/plans/rag-real-estate-mvp.plan.md`.
- **Reviewed 2026-08-10.**

## Verdict: PASS-WITH-WARNINGS

The spine is highly consistent with the web-verified research report. Every AD that names a technology (PG RLS, Llama Prompt Guard 2, RAGAS, Langfuse, Arize Phoenix, Viettel Cloud VPS, PGTableGraphStorage, RobustRAG, Azure Prompt Shields) maps 1:1 to a cited claim in the research report. No contradictions with the source of record were found. The warnings are: one version floor that disagrees with LightRAG's own documented support, and a few un-verified "latest"/version cells in the Stack table that are asserted rather than researched.

---

## Stack section — verified claims (consistent, no action)

| Row | Spine claim | Check | Status |
|---|---|---|---|
| `lightrag-hku 1.5.6 (LOCK)` (L119) | v1.5.6, 2026-08-06, Python ≥3.10 | library-research §1 — PyPI tag v1.5.6 confirmed | PASS |
| `aibox text-embedding-v4 dims 1024 (LOCK)` (L123) | dims configurable 64-2048, default 1024; 1024 chosen to match Qwen3-Embedding-0.6B fallback | library-research §3 + spine AD-2 | PASS |
| `aibox qwen3-rerank POST /v1/rerank` (L124) | Jina/Cohere-compatible; LightRAG `generic_rerank_api` response_format="standard" | library-research §4 | PASS |
| `Llama Prompt Guard 2 22M (CPU) / 86M` (L125) | 86M AUC .998; 22M 19.3ms CPU; screens input + retrieved chunks; ⚠️ tiếng Việt unverified | research report §1.2/§1.3 + AD-6 | PASS |
| `RAGAS latest (CI mode)` (L126) | `evaluate(..., in_ci=True)`, `@pytest.mark.ragas_ci`, PR/nightly split | research report §4.1 + AD-8 | PASS |
| `Langfuse (self-host) + Arize Phoenix (latest)` (L127) | Langfuse MIT self-host traces/cost; Phoenix embedding-drift | research report §4.4 | PASS |
| `Viettel Cloud VPS + Docker Compose` (L128) | Viettel DC Software Park 02 Quang Trung ĐN; self-managed PG; PowerNet fallback; price caveat | research report §5 + AD-9 | PASS |
| `PostgreSQL (pgvector) 15+` (L120) | **See W1 below** | storage-pipeline-research §1 | **WARN** |

## AD-level technology claims — verified (consistent, no action)

- **AD-1 PGTableGraphStorage** — matches storage-pipeline-research §1 (v1.5.6+, plain PG tables JSONB, no Apache AGE, ~20x faster than AGE, PR #3103). Note: the spine correctly uses `PGTableGraphStorage` (the v1.5.6+ replacement) rather than the older `PGGraphStorage` label that library-research §2 still uses — the spine is on the newer, correct name. PASS.
- **AD-3 lifecycle state machine** — draft→review→approved→published→deprecated→deleted; publish as separate action; delete = cascade. Mirrors research report §2.1 exactly. PASS.
- **AD-4 PG RLS** — `ENABLE/ FORCE RLS`, `NOSUPERUSER + NOBYPASSRLS`, `SET LOCAL app.user_id` (param `true`, dies at transaction end), fail-closed 0 results, canary rows, metadata ACL copied per-chunk at ingest. Mirrors research report §2.3 (kawshik.dev hardening list) exactly. PASS.
- **AD-5 seven-role model + uploader≠approver (NIST SSD)** — matches research report §2.2 role table + NIST ANSI INCITS 359. `editor` role is an addition beyond the report's role list but appears in the report's §2.2 table too (editor/contributor). PASS.
- **AD-6 4-layer defense** — L1 Prompt Guard 2 both input+chunks; L2 instruction hierarchy + delimiters + JSON-encode + never concat retrieved content into system prompt; L3 3-5 chunks, SHA-256 + provenance allowlist + invisible-Unicode scan; L4 grounding + audit; `max_total_tokens` 8-12k as blast-radius limit. All mirror research report §1.2 bullets. "PoisonedRAG/HijackRAG ~5 passage/target" matches §1.1. PASS.
- **AD-7 content-addressed incremental** — SHA-256 per chunk, stable `doc_id:chunk_index` IDs, replace-mode start, full rebuild on embedding change, `text_hash` column. Mirrors research report §2.1 + storage-pipeline-research §2. PASS.
- **AD-8 golden-set versioning / re-baseline / CI split** — mirrors research report §4.1. Faithfulness floor 0.96 regulated matches §4.3. **See W3 on threshold provenance.**
- **AD-9 Viettel VPS** — 2-4 vCPU/4GB ≈235-315k, PowerNet ≈292k-456k, DC Software Park 02 Quang Trung, defer managed vDBS (~450k), price caveat "quote vendor trước khi chốt". Matches research report §5 + its single-source price warning. PASS.
- **Deferred: RobustRAG / Azure Prompt Shields** — both match research report §1.2 (RobustRAG +K LLM calls latency tradeoff; Azure Prompt Shields no Vietnamese test). PASS.

---

## Findings

### W1 — MEDIUM: Stack "PostgreSQL (pgvector) **15+**" contradicts LightRAG's documented support floor (16.6+)
- **Line:** 120 (Stack table).
- LightRAG v1.5.6 docs (`docs/ProgramingWithCore.md`, verified in storage-pipeline-research §1): "**PostgreSQL version 16.6 or higher is supported**." The spine states "15+", which implies PG 15 is acceptable. It is not per LightRAG's own support statement. (There is a nuance: `PGTableGraphStorage` as plain tables works on PG 14+ generally, but the LightRAG-supported floor is 16.6+.) If a deployer provisions PG 15 — especially because the research report notes Viettel managed vDBS caps at PG 15 — they land on an unsupported combo. The spine's own AD-9 (self-managed PG on VPS) is unaffected by the vDBS cap, so there is no reason to keep 15 as the floor.
- **Fix:** change to `16.6+` (or `17/18`), matching storage-pipeline-research §1's own recommendation ("PG 16.6+ (hoặc 17/18)").

### W2 — LOW: `FastAPI + uvicorn  pin latest (2026-08)` is an un-verified placeholder, not a pin
- **Line:** 122 (Stack table).
- No research file covers FastAPI/uvicorn versions; the cell asserts "pin latest (2026-08)" with no actual version number, so there is nothing that could have been checked against the web. Greenfield FastAPI is uncontroversial, but the row reads as verified when it is a placeholder. Risk is low, but per the project's own rule of pinning (LightRAG 1.5.6, embedding model), the FastAPI/uvicorn version should either be pinned to a concrete version or explicitly marked "unverified — pin at implementation".

### W3 — LOW: AD-8 CI thresholds (0.05 delta / 2% recall@10) are stated as rule, but research marks them single-source
- **Line:** 92 (AD-8).
- The research report's GAP note (§4.1) explicitly flags "chưa có nguồn phổ dụng cho 'X% drop = fail CI'"; 0.05 delta (Alok) and 2% recall@10 (AmtocSoft) are single-source starting points. The spine states them as the CI gate ("khoảng 0.05 delta hoặc 2% recall@10"). It is partially mitigated — the Deferred table says "Calibrate theo baseline riêng" — but unlike AD-9 (which carries an explicit "Giá từ AI-synth single-source — bắt buộc quote" caveat), AD-8 does not flag its numbers as single-source. Add the same provenance caveat for consistency.

### W4 — LOW: `Ubuntu 22.04 LTS` (Deploy row) is asserted from training data, not in any research file
- **Line:** 128 (Stack table).
- No research file names an Ubuntu version; 22.04 LTS is a training-data default. As of 2026-08, 24.04 LTS is the current LTS (22.04 remains supported until 2027, so this is not an error — but the choice is unverified and arguably stale). Either state 24.04 LTS or mark the row unverified. Docker Compose itself is unremarkable and matches the plan's deploy intent; no issue there.

### W5 — LOW (informational): `RAGAS / Langfuse / Phoenix "latest"` cells
- **Line:** 126-127.
- Tool existence and roles are verified by the research report (§4.4), but no versions are pinned anywhere. For a CI gating tool (RAGAS) and an eval stack, "latest" is a moving target that can silently change eval behavior — the project's own rule 4 (golden-set regression on every LightRAG upgrade) implies the same discipline should apply to eval/obs tooling. Not a contradiction with the report; a pinning note only.

---

## Non-findings (checked, no issue)

- **MinerU/Docling (structural seed, mermaid)** — not in the guardrails report, but established in the plan and prior research as the parser choice; not questionable.
- **No contradiction anywhere with the research report.** The spine's ADs are faithful restatements of the report's cited sections.
- **Embedding base-URL caveat** (api-box.vn vs api.ai-box.vn) surfaces in library-research §3 but is an implementation-time curl check, not an architecture decision; spine correctly leaves it to implementation.

## Summary

One MEDIUM (PG version floor should be 16.6+, not 15+), three LOW (unverified FastAPI/uvicorn "pin", single-source CI thresholds without provenance caveat, Ubuntu 22.04 as an unverified training-data default), one informational (unpinned eval/obs tooling). Everything else in the Stack and ADs is consistent with the web-verified research report.
