# Plan Review Findings — vòng adversarial-verify FINAL PLAN v1.0 (2026-08-10)

> Output workflow ultracode `verify-final-plan-rag-bds` (19 agents: 5 lens review → dedup 44 → 13 skeptic verify → critic vòng 2).
> **13/13 critical/high findings CONFIRMED** (skeptic không bác được). File này = input bắt buộc cho FINAL PLAN v2.0.
> Run: wf_c73f2a35-492 | Plan được review: `.claude/plans/rag-real-estate-final.plan.md` (v1.0 DRAFT).

## A. 13 findings CONFIRMED (bắt buộc fix trong v2)

### A1 (high, lightrag) — ainsert pre-chunk bị Fix re-chunk
`ainsert` LUÔN chunk F (fixed token), không chọn được R/V/P; "FIX 1200/overlap 200 giữ làm fallback" là sai — F là chunker ĐANG chạy. Unit pre-chunk >1200 token bị cắt vỡ Điều/Khoản; placeholder `⟦FACT:...⟧` (nhiều tiktoken) có thể bị chẻ giữa 2 chunk.
**Fix:** truyền `chunking_func` identity/passthrough (escape hatch cho ainsert(text) trực tiếp — ref §1.5) + hard cap mọi pre-chunk ≤ min(1200, embedding max_token) + Điều dài tách theo Khoản + verify placeholder-integrity (regex `⟦FACT` thiếu `⟧` = fail).

### A2 (high, lightrag) — không có mapping chunk_id/doc_id LightRAG ↔ registry
Không pin `ids=[chunk_id]` / `file_paths=[doc_id]` khi ainsert → post-filter JOIN documents không được, citation không resolve, `adelete_by_doc_id` không gọi được.
**Fix:** `ainsert(input=[...], ids=[chunk_id...], file_paths=[doc_id...])` 1:1; thêm cột `documents.lightrag_doc_id`; chân RAG đọc `raw_data.chunks` (KHÔNG dùng context string ghép) để filter từng chunk; verify id khớp Day 3-4.

### A3 (high, lightrag) — token budget: thiếu max_entity_tokens/max_relation_tokens
Default 6000/8000 → tổng 14000 > budget 8-12k; quy tắc `entity+relation < total`, nếu total ≤ entity+relation → chunk budget ≤ 0 → context KHÔNG có chunk → vỡ hydration + grounding.
**Fix:** QueryParam set đủ 3: khởi điểm chân RAG `max_entity_tokens=2000, max_relation_tokens=2000, max_total_tokens=6000`; 8-12k là TỔNG generation (RAG_CONTEXT + FACT_EVIDENCE + system + user).

### A4 (high, security) — facts ACL chỉ app-level JOIN, hydration xuyên qua
Không có DDL RLS cho facts/fact_subjects/campaigns; hydration đọc facts trực tiếp chỉ check interval → fact từ doc expired vẫn hydrate.
**Fix:** ENABLE+FORCE RLS facts/fact_subjects/campaigns; policy SELECT `USING (EXISTS doc published)`, per-command (INSERT/UPDATE WITH CHECK, DELETE USING) theo AD-4; fail-closed khi thiếu identity.

### A5 (high, security) — ORDER BY injection + subject_type chưa validate
`dir` dán thẳng sau SQL parameterized; subject_type điều khiển allowlist cũng chưa validate.
**Fix:** validate closed-set TRƯỚC khi build: subject_type ∈ CHECK constraint; `dir` map dict {"asc":"ASC","desc":"DESC"} (không Identifier, không concat raw); order_by.field ∈ allowlist; limit ∈ [1,20] default 10.

### A6 (high, lifecycle) — thứ tự ingest vi phạm FK
Bước 4 ghi facts (source_chunk_id FK) TRƯỚC document_chunks (bước 6) → INSERT fail; ainsert nằm ngoài transaction registry.
**Fix:** 1 thứ tự: documents → fact_subjects → document_chunks (chunk_id deterministic `doc_id:version:index`, ON CONFLICT idempotent) → facts → chunk_fact_refs → campaigns → COMMIT; LightRAG ainsert CHẠY SAU COMMIT (connection pool riêng), fail → retry idempotent + ingest_log.

### A7 (high, lifecycle) — cascade delete bị FK NO ACTION chặn
facts.source_doc_id / campaigns.source_doc_id / facts.source_chunk_id KHÔNG có ON DELETE → xóa documents lỗi FK; §2.5 "expire facts" vs edge-18 "cascade delete" mâu thuẫn.
**Fix:** chọn hard-delete, thứ tự explicit 1 transaction + rowcount assert: DELETE facts → document_chunks → documents → `adelete_by_doc_id`; campaigns.source_doc_id = fail-loud (chặn xóa doc đang có campaign active, phải expire campaign trước).

### A8 (high, completeness) — range/approx filter semantics undefined
Fact quality='range' (value_num NULL, range_min/max) nhưng sql_spec exact op → match cột nào không định nghĩa; order_by trên range vô nghĩa.
**Fix:** §3.4.1 match_semantics(op, fact) có unit test: `<=` match nếu range_min ≤ value; `>=` nếu range_max ≥ value; between = interval overlap; `in` chỉ categorical; FACT_EVIDENCE kèm quality + range; answer disclosure "khoảng 1.8-2.2 tỷ, có phần vượt 2 tỷ".

### A9 (high, completeness) — RLS identity chỉ chân SQL; hydrate/post-filter không rõ identity
AD-4 fail-closed mà hydrate thiếu identity → 0 rows âm thầm → placeholder nào cũng "không có dữ liệu".
**Fix:** MVP single-tenant: policy query-time STATIC `status='published'` + interval, KHÔNG phụ thuộc app.user_id; `SET LOCAL app.user_id` = defensive multi-tenant; khi bật identity-based → helper `with_rls_identity()` chung cho SQL leg + hydrate + post-filter, fail LOUD (cờ acl_degraded), không 0 rows âm thầm.

### A10 (high, ops) — verify "50-100 văn bản" ảo, seed chỉ 3
**Fix:** smoke 8-12 văn bản cụ thể từ taxonomy T4 (31/2024/QH15, 29/2023/QH15, 91/2015/QH13 trích Điều 309-321/328, 27/2023/QH15, NĐ 101/2024, NĐ 96/2024, NĐ 99/2022, TT 04/2024/TT-BXD + 1 bảng giá mẫu); 50-100 = stretch post-smoke gated trên data-contract §4; parser giữ 1 engine (Docling), MinerU fallback scan xấu.

### A11 (high, ops) — load.py mâu thuẫn chunking (trùng lõi A1)
**Fix:** mỗi Điều/Khoản = 1 element riêng của ainsert([...]) (KHÔNG nối cả văn bản); chunk_token_size constructor ≥ pre-chunk dài nhất + chunking_func identity; parser cắt Điều cực dài tại Khoản (≤ ~2000 token); verify số chunk LightRAG == số pre-chunk.

### A12 (high, ops) — fallback provider đơn độc 'api-box' (cùng họ rủi ro chưa verify)
**Fix:** chain `EMBEDDING_BINDING=dashscope|aibox|local`: DashScope → api-box → local Qwen3-Embedding-0.6B (dims 1024 khớp ADR); rerank optional `RERANK_BINDING=null` + min_rerank_score=0.0 khi fail; chốt endpoint per-provider: DashScope `/v1/reranks` (số nhiều), api-box `/v1/rerank` + `RERANK_BINDING=cohere`.

### A13 (high, ops) — verify commands Day 3-4 không chạy được
**Fix:** `scripts/verify_ingest.sql` cụ thể: authoritative = resolve placeholder (subject_key, fact_key) sang fact tồn tại (KHÔNG lọc hiệu lực — fact expire = cảnh báo, không fail): regexp_matches `'⟦FACT:([^@]+)@([^⟧]+)⟧'` + NOT EXISTS → dangling = 0; check placeholder không có ref; check graph nodes không chứa số giá (query bảng graph của PGTableGraphStorage).

## B. 8 gaps vòng 2 (critic)

1. **(high)** `web/` chat 1 trang KHÔNG có task nào trong 10 ngày + thiếu section API contract → thêm Day 9-10 + contract `{query, session_id, as_of?} → {answer, sources[], facts[], confidence, requires_review, trace_id, latency_ms}` + 4 SSE events.
2. **(high)** Day 1 thiếu env contract LightRAG: POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE/MAX_CONNECTIONS + POSTGRES_VECTOR_INDEX_TYPE=HNSW + POSTGRES_HNSW_M/EF; CREATE DATABASE explicit (LightRAG tạo bảng KHÔNG tạo DB).
3. (medium) document_chunks thiếu `text_hash` (AD-7 re-embed chỉ chunk đổi không có chỗ lưu).
4. (medium) facts.effective_from/to lấy từ đâu chưa định nghĩa → kế thừa documents/campaign interval; LLM trả interval riêng phải validate nằm trong interval doc.
5. (medium) Rerank 2 nơi mơ hồ (enable_rerank internal vs app-side sau post-filter) → chốt 1 nơi + nguồn score cho confidence.
6. (medium) kind='project' không có nhánh trong ingest CLASS → prose → NORM, structured fields → facts.
7. (medium) FACT_EVIDENCE cần campaign nhưng facts không có campaign liên kết → thêm `campaign_key TEXT NULL REFERENCES campaigns` (giá bắt buộc gán campaign).
8. (low) Post-filter RAG leg không tham số hóa as_of → câu hỏi lịch sử mất context quá khứ.

## C. 31 medium/low (chưa verify skeptic — xử lý theo judgment khi viết v2)

lightrag: rerank cần rerank_model_func khi dùng library (nếu không silent off) · update pháp lý = delete-then-reinsert (LightRAG không có API re-embed 1 chunk) · role_llm_configs key đúng là "KEYWORDS" (số nhiều, verify source khi implement) · thiếu addon_params language="Vietnamese" + entity_type_prompt_file (BẮT BUỘC cho legal VN) · mode mix khuyến nghị khi rerank bật + enable_content_headings · thiếu POSTGRES_* env (trùng B2).
security: value_text free-text phải JSON-encode trong FACT_EVIDENCE · graph poisoning qua literal `⟦FACT:...⟧` trong source attacker (sanitize/escape trước khi thay span) · injection ép needs_sql=false → số không grounded vẫn ra answer (L4 phải chặn: câu có số tài chính mà thiếu FACT_EVIDENCE → refuse/downgrade) · field→SQL mapping pivot fact_key vs column chưa rõ · audit sql_spec chứa PII cần redaction + append-only enforce · as_of string tự do chưa validate format.
lifecycle: expire+insert phải CÙNG 1 transaction (khoảng trống đọc) · citation grounding so hydrated text hay raw chunk chưa rõ (chốt: hydrated) · hydration không filter documents.status (trùng A4) · dangling token scan khi subject xóa.
completeness: cold-start refusal UX ("chưa có" vs "chưa nạp") · thiếu aggregate count/min/max/sum ("có bao nhiêu căn dưới 2 tỷ") · eval RAGAS contexts phải gồm FACT_EVIDENCE cho câu fact-lookup · thiếu P95 latency budget · subject_key không normalize/dedup (LLM sinh 'A10-01' vs 'A10.01') · volatile misclassification (số stable đổi giá trị sau → chunk stale) · history window không định nghĩa (budget/turns) · SSE thiếu request.is_disconnected() · as-of lịch sử: chân RAG trả chunk bản hiện tại (disclosure).
ops: Day 9 quá tải (soạn 50 câu + gold_chunk_ids + run_eval trong 1 ngày) → dời soạn golden từ Day 6 · dependencies chưa pin (asyncpg+psycopg 2 driver, MinerU/Docling torch nặng, RAGAS) · nginx/gunicorn --timeout 0 + proxy_read_timeout · PG tuning postgresql.conf (shared_buffers/maintenance_work_mem cho HNSW build) · bộ 20 câu injection test VN chưa gán người/file.

## D. Việc áp dụng

Mọi mục A + gaps high (B1, B2) PHẢI vào FINAL PLAN v2.0. Mục B/C: judgment khi viết, ghi rõ cái nào defer (kèm lý do) — không bỏ thầm.
