# Adversarial Review — ARCHITECTURE-SPINE.md (rag-real-estate)

- **Reviewed:** 2026-08-10
- **File:** `docs/architecture/architecture-rag-real-estate-2026-08-10/ARCHITECTURE-SPINE.md`
- **Lens:** Attack the spine as an adversary — construct two units one level down that each obey every AD to the letter yet still build incompatibly. Every pair found is a hole to close with a new or tightened AD.
- **Verdict:** **FAIL** (as build-substrate as written) — two CRITICAL pairs directly contradict the spine's own stated invariant "Security boundary nằm ở retrieval-time (trong DB)". Recoverable via the tightenings below.

---

## Method

For each pair: **Unit A** (obeys AD-x/A-D-y) × **Unit B** (obeys AD-i/AD-j) → the concrete incompatibility at build time → the hole → which AD to tighten / which new AD to add.

---

## F1 — CRITICAL — AD-4 × AD-3/AD-7: the AD-7-mandated deletion path is a silent no-op under AD-4's fail-closed RLS

**Unit A (chunk writer / delete path):** obeys AD-7 (replace mode = "delete all chunks của doc + re-index", delete by ID, idempotent+resumable) and AD-3 (`deleted` → cascade delete chunks+embeddings). Runs as the single app runtime role `NOSUPERUSER NOBYPASSRLS` — AD-1 mandates one backend, so one role serves both ingest and query.

**Unit B (row security):** obeys AD-4 — `FORCE RLS` on chunk tables, identity only from `SET LOCAL app.user_id`, chunk `acl_roles` copied at ingest, **fail-closed: check fail → 0 results, no fallback**.

**Clash:** RLS `USING` clauses apply to DELETE/UPDATE as much as SELECT. When replace-mode deletes the old chunks of a doc, the policy evaluates `app.user_id` against the *old* rows' `acl_roles` — which were copied at the previous ingest under a different actor (or a headless pipeline transaction with no `SET LOCAL` identity at all). The DELETE matches 0 rows silently. The stale chunks remain in the vector index; the query path still retrieves them. Both units "obey" their ADs and the result is exactly the failure AD-3 was created to prevent (old version sitting next to new in the index) — and AD-4's fail-closed is what makes the failure *silent* (a loud permission error would have surfaced it).

**Tighten AD-4:** declare RLS policies **per command type** — `SELECT` uses ACL `USING`; `INSERT ... WITH CHECK` and `UPDATE/DELETE` use a distinct policy scoped to the ingest pipeline role **within the same transaction that sets identity**, and every replace-mode delete must assert affected-rowcount == expected (fail loud, not silent). **Or tighten AD-7:** deletions run as a dedicated maintenance role with `DELETE`-only bypass, and replace-mode aborts if the deleted count ≠ expected count.

---

## F2 — CRITICAL — AD-4 × AD-1/AD-6: the graph leg of hybrid retrieval sits outside the RLS boundary

**Unit A (retrieval):** obeys AD-1 (`PGTableGraphStorage` — plain PG tables, JSONB, content-addressed) and AD-6 (hybrid dual-level retrieval, 3-5 chunks, low-level entity + high-level theme).

**Unit B (ACL):** obeys AD-4 — RLS on *chunk tables*, ACL metadata (`roles`, `sensitivity_classification`, `org`) copied onto **each chunk**.

**Clash:** `PGTableGraphStorage`'s entity/relation rows are shared, content-addressed, and carry **no `acl_roles`/`org` column** — AD-4's ACL copy is defined only for chunks. Hybrid dual-level retrieval pulls entities/relations from the graph store and reuses them as context; nothing in the DB filters a viewer's graph context by identity. A viewer entitled only to doc X receives entity/theme context assembled from restricted doc Y via shared nodes (in a legal corpus, "Luật Đất đai 2024" is a node shared by hundreds of docs across sensitivity levels). The claim "Security boundary nằm ở retrieval-time (trong DB)" is false for the graph leg — the graph leg is effectively an un-ACLed side channel.

**Tighten AD-4 (or new AD-12):** ACL must extend to graph provenance — entity/relation rows carry `source_doc_ids`, and any graph context entering the prompt must be joined (inside the DB) against the chunk-level permitted doc set; or AD-6 must restrict graph-based context to the doc set already authorized by the chunk RLS pass. State the invariant explicitly: *no graph context may be injected into the prompt unless its provenance doc IDs ⊆ the viewer's RLS-permitted set.*

---

## F3 — HIGH — AD-7 × AD-8/AD-10: "stable" chunk ID `doc_id:chunk_index` is *positional*, so golden-set and audit citations silently re-point after a mid-doc edit

**Unit A (update_6mo.sh):** obeys AD-7 (replace mode, stable chunk IDs, upsert by ID) and AD-8 (re-baseline: run eval BEFORE/AFTER, compare delta).

**Unit B (eval + audit):** obeys AD-8 (golden set versioned with corpus, answers tied to sources) and AD-10 (audit log records chunk IDs for replay).

**Clash:** delete chunk at index 3 of a doc → indices 4,5,… shift left; `doc_id:3` now holds *different text and embedding* under the same ID. Golden-set rows citing `doc_id:3` — and faithfulness scoring against that chunk — now ground against different content. That is precisely the "eval silently stops measuring" failure AD-8 was designed to kill, reappearing at chunk granularity. The BEFORE/AFTER delta cannot detect it because both runs use the same now-shifted IDs. Audit replay of a pre-update answer joins post-update chunk IDs → citations no longer groundable (AD-10's replayability is broken).

**Tighten AD-7:** chunk identity must be **content-stable, not positional** — e.g. `doc_id:version:chunk_index`, where any net content change bumps `version` (replace mode already distinguishes re-index). **Tighten AD-8:** golden-set citations must pin `(doc_id, version | content_hash)`, not bare `chunk_index`; any doc whose content-hash set changed must have its cited golden rows re-labeled rather than silently re-run. **Tighten AD-10:** audit's cited chunk IDs must include the version so replay resolves to the exact content that was answered.

---

## F4 — HIGH — AD-5 × AD-3: metadata edits after legal sign-off + an undefined publish actor ⇒ "publish = separate action" does not enforce SoD

**Unit A (document-manager flow):** obeys AD-5's role list — `document_manager` may "upload/sửa metadata/submit review"; `legal_approver` gives final sign-off and must differ from uploader (NIST SSD).

**Unit B (lifecycle):** obeys AD-3 — `approved → published` is a separate action; only `published` enters the live index.

**Clash (two incompatibilities in one pair):**
1. AD-5 permits the manager to edit metadata (including `acl_roles`, `effective_date`, `version`) with no boundary, and AD-3's transition table has no "locked" state. Manager edits `acl_roles` after review → legal_approver signs off the *text* → the published ACL differs from the approved ACL. Reviewer approved content; a different ACL shipped. Compliance hole, both units in compliance.
2. AD-5 never names who executes the `approved→published` transition. If the approver also runs the publish step ("separate action" but **same actor, one click**), NIST SSD is violated while the role list is satisfied. In a small team one person holds 2+ roles — "enforce by policy application" is empty without a per-person mutually-exclusive-role rule.

**Tighten AD-3:** `approved` pins a snapshot — `acl_roles`/`effective_date`/content-hash become immutable at approval; any change forces revert to `review`. **Tighten AD-5:** name the publish actor; require **publisher ≠ approver ≠ uploader** (three distinct identities), enforced as a DB constraint inside the transition procedure (`current_user` vs stored uploader/approver), plus a policy that a single person cannot hold more than one of {document_manager, reviewer, legal_approver, publisher}.

---

## F5 — MEDIUM-HIGH — AD-9 × AD-10/AD-8: one 4GB VPS cannot host "dev/staging/prod tách biệt", and the eval DB identity is undefined against AD-4

**Unit A (deploy):** obeys AD-9 — single self-managed Viettel VPS 2-4 vCPU/4GB, PG on the same box, "Env: dev/staging/prod tách biệt", managed vDBs deferred.

**Unit B (ops hygiene + eval):** obeys AD-10 ("Cấm ghi prod DB từ test; secrets chỉ qua env") and AD-8 (nightly full 4-metric eval) and AD-4 (RLS fail-closed: no identity → 0 rows).

**Clash (two bites):**
1. Three separated environments need ≥3 PG instances + ≥3 app stacks + Langfuse + Arize Phoenix (Stack table) — 4GB will not run that. The only budget-honest reading is same-box/same-PG separation, which makes "cấm ghi prod từ test" a convention, not an enforcement — one misconfigured `DATABASE_URI` string is all it takes. The deploy that obeys AD-9 cannot enforce AD-10's separation.
2. The nightly full eval (AD-8) must query the corpus — **as what identity?** The spine defines eval but never defines eval's DB role. As the plain app role with no `SET LOCAL app.user_id`, AD-4 fail-closed returns 0 rows and the eval measures nothing; as a privileged/bypass role, it violates AD-4's "NOBYPASSRLS" and AD-10's separation.

**Tighten AD-9:** pin the env topology inside the budget — dev = developer machine, staging = separate schema/container on the VPS gated by an env flag, prod = the box; and either drop self-hosted Langfuse/Phoenix from the MVP or raise the RAM line. **Add a new AD (AD-11):** a purpose-built `eval` DB role with its own RLS policy (read published + authorized, write only to eval tables) used by CI/nightly — that is the only way eval passes AD-4 while satisfying AD-10.

---

## F6 — MEDIUM — AD-3 × AD-1: "deleted → cascade delete graph nodes" collides with the shared content-addressed graph store

**Unit A (deletion):** obeys AD-3 — cascade delete chunks + embeddings + **graph nodes** + cached responses on `deleted`.

**Unit B (graph store):** obeys AD-1 — `PGTableGraphStorage` merges nodes/edges by shared keys across documents (content-addressed, no per-doc ownership).

**Clash:** in a legal corpus, one entity ("Luật Đất đai 2024", "QSDĐ") is a node shared by hundreds of docs. Deleting doc A cascades the shared node → doc B's provenance edges vanish (over-delete). Making the cascade skip shared nodes → doc A's entity context remains retrievable (under-delete, feeding F2's leak). The spine has no refcount/ownership model for graph nodes.

**Tighten AD-3 (or fold into new AD-12):** cascade applies to *doc-provenance edges and per-doc chunk/embedding rows*; nodes garbage-collect only when no document references remain (refcount on `source_doc_ids`).

---

## F7 — MEDIUM — AD-2 × AD-7/AD-4: resumable replace leaves `is_current=false` rows that the query path can still retrieve

**Unit A (indexer):** obeys AD-7 (job idempotent + resumable, replace mode, per-chunk content-hash) and AD-2 (per-row `model_name/model_version/is_current`).

**Unit B (query):** obeys AD-4 (RLS policy on ACL only) and AD-6 (hybrid retrieval).

**Clash:** a resumable replace that dies mid-doc leaves the doc with mixed old/new embeddings; old rows marked `is_current=false` still sit in the vector table. AD-4's `USING` clause filters on ACL only — nothing filters `is_current` — so retrieval can return stale-embedding vectors whose distances are meaningless (two embedding spaces, exactly AD-2's stated fear). The `published` gate (AD-3) checks status, not embedding currency.

**Tighten AD-4 + AD-7:** the retrieval condition must include `is_current = true` (RLS or a mandatory query-path predicate); AD-7 must make "every chunk of the doc carries the current embedding" a precondition of the `published` transition (atomic publish gate), and replace-mode must delete old embedding rows in the same transaction as the insert.

---

## Synthesis — the two clusters

1. **The RLS-as-single-boundary cluster (F1, F2, F7):** AD-4's fail-closed RLS is declared the one security boundary, yet (a) the write path is also RLS-filtered and therefore silently broken, and (b) storage that can enter the prompt — graph nodes (F2) and stale embeddings (F7) — is invisible to RLS. AD-4 needs per-command scoping plus a *coverage statement*: every row that can enter the prompt must be RLS-visible or provenance-joined.
2. **The identity-vs-stability cluster (F3, F4):** positional chunk IDs undermine AD-8/AD-10 citation stability; AD-5's roles don't constrain the publish actor; AD-3's states don't pin reviewed content.

**Recommended new ADs:** **AD-11** (eval/test DB identity + eval role policy) and **AD-12** (graph node provenance/refcount + ACL join). **Tighten:** AD-4 (per-command policies + coverage statement + `is_current`), AD-5 (publish actor, 3-distinct-identities, mutually-exclusive roles), AD-7 (content-stable chunk identity + loud rowcount asserts), AD-9 (env topology + capacity vs Stack table), AD-3 (approval snapshot lock + graph refcount).
