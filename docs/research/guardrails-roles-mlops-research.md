# Deep Research: Guardrails, Document Roles, AI-Engineering Rules, MLOps & Deploy tại Đà Nẵng

*Ngày: 2026-08-10 | Dự án: rag-real-estate (LightRAG + FastAPI + PostgreSQL) | Sources: 5 agents, ~40+ nguồn web | Confidence: High (đa nguồn hội tụ) / Medium (một số số liệu đơn nguồn, đã đánh dấu)*

> Báo cáo này trả lời 6 trụ bạn yêu cầu: (1) guardrails chống prompt injection, (2) roles quản lý tài liệu,
> (3) best practices RAG legal, (4) rules AI-Engineering ràng buộc agents, (5) MLOps đẩy lên theo sprint,
> (6) dịch vụ deploy uy tín tại Đà Nẵng. Mỗi mục kèm khuyến nghị tích hợp vào project hiện tại.
> File: `docs/research/guardrails-roles-mlops-research.md`

---

## Executive Summary

1. **Prompt injection qua tài liệu (indirect) là rủi ro #1 của RAG** — không có defense đơn lẻ nào đủ; phải
   defense-in-depth theo 4 lớp (input → prompt construction → retrieval → output). Cho legal RAG: bộ lọc
   poisoned chunk + instruction hierarchy + citation grounding + audit log là bắt buộc.
   ([OWASP RAG Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html),
   [Microsoft MSRC](https://www.microsoft.com/en-us/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks))

2. **Access control phải thực thi ở retrieval-time, trong database (PG RLS), không phải ở UI hay LLM output** —
   "không được đưa doc không được phép vào prompt, chứ không phải chỉ không hiển thị ra output".
   Đây là lỗi compliance phổ biến nhất của enterprise RAG. ([OWASP §4](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html),
   [AWS Security](https://aws.amazon.com/blogs/security/authorizing-access-to-data-with-rag-implementations/),
   [kawshik.dev](https://kawshik.dev/blog/multi-tenant-rag-pgvector-postgres-rls.html))

3. **Thiếu 1 state machine lifecycle cho tài liệu** (draft → review → approved → published → deprecated → deleted):
   chỉ `published` mới vào vector index; tài liệu expired/hết hiệu lực phải loại khỏi retrieval, không phải chỉ ẩn UI.
   Role model chuẩn: admin / document manager / reviewer(SME) / legal approver / viewer / auditor, với
   **uploader ≠ approver** (separation of duties theo NIST RBAC ANSI INCITS 359). ([NIST RBAC](https://csrc.nist.gov/projects/role-based-access-control),
   [knowledge-base.software](https://knowledge-base.software/guides/knowledge-base-governance-framework/))

4. **Ràng buộc agents = enforcement layer (hooks/permission), không phải lời khuyên trong CLAUDE.md** —
   "Hooks are law, CLAUDE.md is advisory". Quy tắc: plan-first → approve → implement → review; cấm push/commit
   không được yêu cầu; cấm lệnh destructive; test bắt buộc trước merge; scope discipline; sandbox; approval gate
   cho irreversible/externally-visible. ([Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents),
   [Anthropic How we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude),
   [Claude Code hooks](https://code.claude.com/docs/en/hooks-guide))

5. **MLOps: "Evals are CI"** — golden set chạy trong CI, block merge khi score tụt; split suite (PR gate = faithfulness
   + answer relevancy trên subset; nightly = full 4 metric). Deploy theo sprint: shadow → canary 1→5→25→100% với
   auto-rollback watcher → blue-green standby 24-72h. **⚠️ 6 tháng update 1 lần = "eval invalidation paradox"**:
   update corpus làm golden set cũ mất ý nghĩa → phải version golden set cùng corpus, re-baseline. ([RAGAS CI](https://docs.ragas.io/en/latest/howtos/applications/add_to_ci/),
   [DevOpsNess](https://www.devopsness.com/blog/shadow-testing-and-canary-releases-for-llm-changes),
   [tianpan.co](https://tianpan.co/blog/2026-05-07-rag-eval-invalidation-corpus-update-paradox))

6. **Đà Nẵng: Viettel Cloud là lựa chọn số 1** — duy nhất có cả Data Center tại Đà Nẵng (Tòa nhà Software Park,
   02 Quang Trung, Hải Châu) VÀ managed PostgreSQL (vDBS). Chi phí ~700k-1.7M VND/tháng cho 2-4 vCPU + PG.
   Phương án rẻ: tự quản PG trên VPS Viettel (4vCPU/4GB ≈315k) hoặc PowerNet (local, 292k-456k). VNPT (An Đồn DC)
   và FPT (nhưng giá mờ) là phương án thay thế. ([Viettel vDBS](https://viettel-cloud.com.vn/viettel-database-service-en/),
   [colomap Viettel Danang DC](https://colomap.com/facilities/viettel-danang-dc/))

---

## Phần 1. Security & Guardrails chống prompt injection

### 1.1 Attack vectors của RAG chatbot

| Vector | Mô tả | Mức độ |
|---|---|---|
| **Indirect / document prompt injection** | Kẻ tấn công giấu lệnh trong tài liệu được retrieve, override system prompt. "Most common and immediately exploitable RAG attack vector" — bất kỳ KB dùng chung có upload đều rủi ro | 🔴 #1 |
| **Direct prompt injection** | User input kiểu "ignore previous instructions", persona replacement, encoding (Base64/multilingual/typoglycemia) | 🔴 Cao |
| **Data exfiltration / prompt leakage** | Hỏi model để lộ system prompt, hoặc lén nhúng dữ liệu vào image URL gửi ra ngoài | 🔴 Cao |
| **Query-driven corpus probing** | Craft query để dò tài liệu nhạy cảm trong vector store (recon) | 🟠 Trung |
| **Knowledge base poisoning** | Chèn văn bản đối nghịch vào corpus điều khiển câu trả lời (PoisonedRAG, HijackRAG — chỉ cần ~5 passage/target query, transferable) | 🔴 Cao |

Tài liệu quan trọng: [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html),
[OWASP GenAI LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/),
[Microsoft: indirect injection không thể loại bỏ hoàn toàn → defense-in-depth](https://www.microsoft.com/en-us/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks),
[HOUYI (Liu et al.)](https://arxiv.org/abs/2306.05499), [Rag-n-Roll: ~40% attack success rate](https://doi.org/10.48550/arxiv.2408.05025),
[PoisonedRAG](https://arxiv.org/html/2508.02835), [HijackRAG](https://arxiv.org/html/2410.22832)

### 1.2 Defense theo 4 lớp (defense-in-depth)

**Lớp 1 — Input:**
- **Llama Prompt Guard 2 (Meta)** — classifier injection/jailbreak, bản 86M (AUC .998, đa ngôn ngữ) và 22M (**19.3ms latency, rẻ hơn 75%**, chạy CPU). Screen cả user input lẫn retrieved chunks.
  ([HF model card](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M))
- **Azure Prompt Shields** — hosted, phát hiện cả direct + indirect injection, có sub-taxonomy. ⚠️ **Ngôn ngữ test: 8 ngôn ngữ, KHÔNG có tiếng Việt → chất lượng trên VN chưa verify.** ([Azure docs](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection))
- **Pre-screen bằng model nhỏ** — Anthropic khuyến nghị dùng Haiku 4.5 + structured-output JSON để classify input harmful/injection trước. ([Anthropic docs](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks))
- **Rate limiting + query normalization** — chặn corpus probing; log identity. (OWASP)

**Lớp 2 — Prompt construction:**
- **Instruction hierarchy** — system > user > third-party content; lower-privilege bị bỏ qua khi mâu thuẫn. ([Anthropic paper](https://arxiv.org/html/2404.13208))
- **Delimiters / spotlighting** — bọc retrieved content trong marker riêng ("treat as data only", `<ref_token>`); XML delimiting giảm injection success ~84% → <15% *(số đơn nguồn, directional)*. ([USENIX 2024](https://www.usenix.org/system/files/usenixsecurity24-liu-yupei.pdf), [aipromptarchitect](https://aipromptarchitect.co.uk/guides/prompt-injection-prevention))
- **JSON-encode untrusted content** — không cho attacker "break out" khỏi quote/tag. (Anthropic)
- ⚠️ **Never concat RAG content vào system prompt** — "commonest production bug". Dùng role messages riêng: system=policy, user=input, tool=retrieved. ([instruction-isolation](https://www.promptinjectionprevention.com/kb/instruction-isolation-best-practices.php))

**Lớp 3 — Retrieval:**
- **Chunk isolation & limits** — 3-5 chunks, 2-4k tokens; tag mỗi chunk là untrusted. (OWASP)
- **Document hashing + provenance** — SHA-256 lúc ingest, verify trước retrieve, allowlist trusted sources, scan invisible Unicode. (OWASP)
- **Poisoned-doc detection** — CleanBase (phát hiện clique ngữ nghĩa của doc độc hại), FilterRAG (lọc adv text, mất ~0.2% perf). ([CleanBase](https://doi.org/10.48550/arxiv.2605.00460), [arXiv 2508.02835](https://arxiv.org/html/2508.02835))
- **RobustRAG (isolate-then-aggregate)** — LLM trả lời từng passage riêng rồi aggregate an toàn; certifiable, attack success <10% vs 90%+ vanilla. **Nhưng +K LLM calls/query → cân nhắc latency.** ([arXiv 2405.15556](https://arxiv.org/html/2405.15556))
- **NeMo retrieval rails** — hook framework level reject/alter chunks trước khi vào LLM. ([NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails))

**Lớp 4 — Output:**
- **Canary tokens** — chuỗi ẩn trong system prompt; nếu xuất hiện ở output → prompt đã bị compromise. (Rebuff concept)
- **Sensitive-data redaction** — PII masking (LLM Guard, Presidio, AWS Bedrock Guardrails).
- **Dual-LLM pattern** — LLM có quyền (privileged) giữ tools nhưng không đọc untrusted content; LLM "cách ly" đọc untrusted nhưng không có quyền hành động. (OWASP)
- **Output screening** — LLM-as-judge chấm response trước khi trả về.
- **Human-in-the-loop cho high-stakes** — deterministic mitigation chống exfiltration. (Microsoft)

### 1.3 So sánh guardrails libraries/tools

| Tool | Loại | Ưu | Nhược | Phù hợp |
|---|---|---|---|---|
| **Llama Prompt Guard 2** | Classifier OSS (86M/22M) | Siêu nhẹ, 19.3ms, CPU, miễn phí | Chỉ label, no control flow | ✅ Screen input + chunks trong FastAPI |
| **NeMo Guardrails** | Runtime framework (Apache-2.0) | **Retrieval + execution rails** độc nhất; programmable | Học Colang; latency cộng dồn | ✅ Retrieval rails cho legal |
| **Guardrails AI** | Output-validation (Apache-2.0) | Enforce structured output (JSON citations) | Không phát hiện injection | ✅ Validate cấu trúc trả lời |
| **Llama Guard 4** | Classifier 12B multimodal | Safety đa năng | ~24GB VRAM, ~0.46s → quá chậm per-request | ❌ Không cho per-request |
| **AWS Bedrock Guardrails** | Managed | **Contextual grounding check** độc nhất (chống hallucination RAG) | AWS-locked | Nếu dùng AWS |
| **Azure Prompt Shields** | Managed | Phát hiện direct + indirect injection | ⚠️ Không test tiếng Việt | Cân nhắc, test VN trước |
| **LLM Guard (Protect AI)** | Scanner | PII anonymization tốt | **Repo archived 2026-07-09** | ❌ Đừng adopt mới |

### 1.4 Best practices legal RAG (đã verify thêm)

1. **Citation grounding + groundedness check** — RAG triad (context relevance, groundedness, answer relevance); AWS Bedrock contextual grounding = filter chặn câu trả lời không grounded. ([OWASP LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection/), [AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html))
2. **Signed source attribution trên mỗi response** — verify grounding span nằm trong source chunk (khớp 100% với rule 2 hiện tại của project). ([OWASP](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html))
3. **Human review high-stakes** — OWASP control #5: "require human approval for high-risk actions". (khớp rule 3 project)
4. **Full-pipeline audit log** — query + identity + retrieval pattern + alerts on injection attempts. (OWASP)
5. **Ingestion governance** — hash + provenance + allowlist nguồn + approval workflow + scan invisible Unicode khi ingest; **fail-closed throughout pipeline**. (OWASP)
6. **Fine-grained permissions giảm blast radius** — "indirect injection relies on app running with same permissions as user" → RBAC per document collection + retrieval-time check. (Microsoft)
7. **Adversarial testing / red-teaming** — chạy test corpus injection (OWASP publish) định kỳ; benchmark mọi guardrail vì "every benchmark degrades under adversarial pressure".

> ⚠️ **GAP**: chưa có nguồn chuẩn hóa cho confidence 3-tier legal — design hiện tại của project (≥2 nguồn, rerank ≥0.8, grounding pass) là hợp lý, nhất quán với groundedness approach, nhưng là quyết định nội bộ.

---

## Phần 2. Roles quản lý tài liệu + RBAC

### 2.1 Document lifecycle trong RAG knowledge base

**State machine bắt buộc** (mô hình Contentstack/Veeva/OWASP): `draft → review → approved → published → deprecated/expired → deleted`

| Phase | Effect với vector index |
|---|---|
| **Draft** (upload) | Ở staging, **KHÔNG vào live index** — "not all content should be retrievable until vetted" ([ChatNexus](https://articles.chatnexus.io/knowledge-base/content-governance-for-enterprise-rag-systems/)) |
| **Review** | Vẫn không retrievable; sửa không gây hậu quả ([Docsio](https://docsio.co/blog/documentation-lifecycle)) |
| **Approved** | Vẫn chưa vào index — **publish/index = hành động riêng biệt** ([Contentstack](https://www.contentstack.com/academy/courses/workflow-branches-and-collaboration/content-lifecycle-draft-review-publish)) |
| **Published (indexed)** | Chunk + embed + ghi vector store. Kèm metadata owner/classification/effective_date/status/version |
| **Deprecated / expired** | **Phải loại khỏi retrieval** (post-filter status/effective_date), không chỉ ẩn UI ([OWASP](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)) |
| **Deleted** | **Cascade delete** toàn bộ chunks + embeddings + cached responses; deletion log; audit orphan chunks (OWASP) |

**Failure mode kinh điển**: "policy doc được update nhưng bản cũ vẫn nằm trong index cạnh bản mới" ([safjan.com](https://safjan.com/version-your-vectors-index-versioning-as-the-missing-layer-in-rag/))

**Versioning (khớp 100% với LightRAG incremental update của project):**
- Content-hash (SHA-256/md5) per chunk → re-embed CHỈ chunk thay đổi (tiết kiệm 60-95% chi phí) ([ai-tldr](https://ai-tldr.dev/learn/embeddings-vector-databases/vectors-in-production/syncing-embeddings-with-source-data/), [TypeGraph](https://typegraph.ai/blog/incremental-re-indexing-rag-change-detection))
- **Stable deterministic chunk IDs** (`doc-id:chunk-index`) → update = upsert by ID, delete = remove by ID ([Qdrant](https://qdrant.tech/documentation/tutorials-operations/incremental-embedding-updates/))
- **Replace mode** (delete all chunks + re-chunk/re-embed) là điểm khởi đầu an toàn hơn upsert ([TypeGraph](https://typegraph.ai/blog/incremental-re-indexing-rag-change-detection))
- **Đổi embedding model = FULL REBUILD, không bao giờ incremental** — trộn vector 2 model = khoảng cách vô nghĩa. Version embedding model per row (`model_name`, `model_version`, `is_current`) + blue-green index + atomic alias swap. ([qaskills](https://qaskills.sh/blog/embedding-drift-monitoring-tests-guide), [dbi-services](https://www.dbi-services.com/blog/rag-series-embedding-versioning-with-pgvector-why-event-driven-architecture-is-a-precondition-to-ai-data-workflows/))
- Legal: **giữ bản cũ cho audit** nhưng đánh non-current + loại khỏi retrieval (per-row `is_current` + partial index). ([dbi-services](https://www.dbi-services.com/blog/rag-series-embedding-versioning-with-pgvector-why-event-driven-architecture-is-a-precondition-to-ai-data-workflows/))

### 2.2 Role model (RBAC) khuyến nghị

| Role | Được làm | Không được |
|---|---|---|
| **admin** | Tạo user, gán role, config storage, force re-index, audit log | Là approver duy nhất cho nội dung legal (SoD) |
| **document manager / curator** | Upload draft, sửa metadata, submit review, quản lý taxonomy, retire/archive | Duyệt bài mình tự upload; publish thẳng |
| **reviewer (SME)** | Review tính chính xác pháp lý, trả về draft với feedback | Final-approve high-risk (cần gate pháp lý) |
| **approver / legal approver** | Final sign-off để publish/retire | Không thể là người đã upload (SoD) |
| **editor / contributor** | Draft và chỉnh sửa | Không publish, không approve |
| **viewer / end-user (mua giới)** | Query qua chat; chỉ thấy published + authorized | Không thấy draft/rejected/retired; không quản lý |
| **auditor** (read-only) | Replay audit trail, verify access decisions | Không sửa gì |

Nguồn: [knowledge-base.software (governance framework)](https://knowledge-base.software/guides/knowledge-base-governance-framework/),
[ChatNexus](https://articles.chatnexus.io/knowledge-base/content-governance-for-enterprise-rag-systems/),
[NIST RBAC (ANSI INCITS 359-2004/2012)](https://csrc.nist.gov/projects/role-based-access-control)

**Nguyên tắc cứng:**
- **Uploader ≠ approver = Static Separation of Duty** (SSD) — một user không thể vừa là document manager vừa là legal approver cho cùng doc. Được hỗ trợ chính thức bởi NIST model. ([NIST](https://csrc.nist.gov/projects/role-based-access-control/role-engineering-and-rbac-standards), [ANSI INCITS 359 PDF](https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/ANSI+INCITS+359-2004.pdf))
- **Metadata contract ngay lúc ingest** (không thêm sau): `owner`, `source_system`, `last_validated_date`, `sensitivity_label`, `version`. "Vector DB không có structured metadata = không thể filter" ([tianpan.co](https://tianpan.co/blog/2026-04-17-enterprise-rag-knowledge-base-governance))
- **Không tài liệu nào sống không owner** — vô chủ = auto-demote khỏi active index. (knowledge-base.software)
- **High-risk legal workflow**: Author → SME → Compliance/legal reviewer → Final approver (3-7 ngày, audit trail + version history). **AI-assisted content: "Never publish without human validation."** (knowledge-base.software)
- **Review trigger theo sự kiện nguồn**, không theo lịch: policy doc đổi → dependent content về lại review. ([tribble.ai](https://tribble.ai/blog/ai-answer-library-governance-approvals-citations-ownership/))

### 2.3 Document-level access control — PG RLS là lựa chọn vàng cho project

**Nguyên tắc lõi (đa nguồn đồng thuận):** *"Access control phải thực thi ở retrieval-time, ở data layer — LLM không bao giờ được nhìn thấy doc không được phép, chứ không phải chỉ không hiển thị output."*
([OWASP §4](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html) — "most common compliance failure in enterprise RAG";
[AWS](https://aws.amazon.com/blogs/security/authorizing-access-to-data-with-rag-implementations/) — "LLMs should be considered untrusted entities";
[tianpan.co](https://tianpan.co/blog/2026-04-17-enterprise-rag-knowledge-base-governance))

**Vì project đã lock PostgreSQL single-backend (PGTableGraphStorage/PGVector là plain PG), PG RLS áp dụng trực tiếp:**
- `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + `CREATE POLICY ... USING (...)`; **không có policy = default deny** ([PostgreSQL docs](https://www.postgresql.org/docs/current/ddl-rowsecurity.html))
- **pgvector queries là SQL thường** → RLS filter tự động áp dụng trong `ORDER BY embedding <=> $1` ([Supabase](https://supabase.com/docs/guides/ai/rag-with-permissions), [kawshik.dev](https://kawshik.dev/blog/multi-tenant-rag-pgvector-postgres-rls.html))
- **Hardening**: runtime role `NOSUPERUSER` + `NOBYPASSRLS`; identity qua `SET LOCAL app.tenant_id` trong transaction (tham số `true` để chết cuối transaction, không rò sang pooled request); **không bao giờ lấy identity từ client-supplied header**; `FORCE ROW LEVEL SECURITY` cho table owner; canary rows test cross-tenant denial. ([kawshik.dev](https://kawshik.dev/blog/multi-tenant-rag-pgvector-postgres-rls.html))
- **Metadata ACL phải nằm trên từng chunk**, copy từ source doc lúc ingest — "embedding là dãy số không biết ai sở hữu" ([Gateco](https://www.gateco.ai/blog/document-level-permissions-enterprise-rag))
- **Fail-closed**: thiếu identity hoặc check fail → trả về KHÔNG GÌ, không fallback model-memory. (OWASP §14)
- **Deny-before-allow semantics** (explicit deny thắng allow). ([kirkryan.co.uk](https://kirkryan.co.uk/item-level-permissions-in-rag-why-your-vector-database-needs-access-control/))
- **Permission-change propagation**: re-sync metadata khi source permission đổi (nightly job hoặc webhook). (OWASP, Kirk Ryan)

### 2.4 Audit trail cho legal

- Phải replay được chuỗi: request → query → retrieval (index, filters, top-k, chunk IDs) → prompt → model → answer → action. ([thomasthelliez.com](https://thomasthelliez.com/blog/rag-governance-source-authority-access-control-auditability/))
- Audit log là "single most requested evidence" trong ISO/HIPAA/financial audits. ([Folderit](https://www.folderit.com/blog/what-is-document-management/))
- Eval governance phải test cả controls (unauthorized access, stale sources, injection, missing citations), không chỉ answer relevance. (thomasthelliez.com)

---

## Phần 3. AI-Engineering rules ràng buộc agents ("không chạy nhong nhong")

### 3.1 Nguyên tắc kiến trúc (Anthropic/OpenAI/Google)

1. **Simplicity first** — "finding the simplest solution possible, only increasing complexity when needed"; single agent trước, multi-agent chỉ khi context pollution/parallelization/specialization thực sự cần (multi-agent tốn 3-10x tokens). ([Anthropic](https://www.anthropic.com/engineering/building-effective-agents), [OpenAI](https://openai.com/index/a-practical-guide-to-building-agents/), [Google](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system))
2. **Workflow khi deterministic, agent khi cần model-driven + có stopping conditions** (max iterations). (Anthropic)
3. **Tool design quan trọng như prompt** — absolute paths, poka-yoke args, examples; fewer well-chosen tools > nhiều tool; >15-20 tools gây context degradation; dynamic tool discovery tiết kiệm tới 85% tokens. ([Anthropic writing-tools](https://www.anthropic.com/engineering/writing-tools-for-agents), [context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents))
4. **CLAUDE.md là context, không phải configuration** — <200 lines, path-scoped rules trong `.claude/rules/`, dùng Skills cho progressive disclosure. ([Claude Code memory](https://code.claude.com/docs/en/memory))

### 3.2 Guardrails bắt buộc (enforcement, không phải lời khuyên)

| Guardrail | Cách làm | Nguồn |
|---|---|---|
| **Scoped permissions / least privilege** | Allow/Ask/Deny rules trong `.claude/settings.json` — **enforced bởi client, không phải model**; deny thắng allow, không override được; check-in git để share team. **Permissions profile hẹp nhất đủ dùng**; deny `.env`/secrets | [Claude Code permissions](https://code.claude.com/docs/en/permissions), [OpenAI Codex permissions](https://developers.openai.com/codex/permissions), [Okta](https://www.okta.com/identity-101/how-to-implement-least-privilege-for-ai-agents/), [NVIDIA](https://developer.nvidia.com/blog/four-ways-to-deploy-more-secure-ai-agents/) |
| **Hooks là "luật", CLAUDE.md là "lời khuyên"** | `PreToolUse` hook (exit 2 / deny) chặn tool ngay cả ở bypassPermissions: block `.env`, `package-lock.json`, `.git`, `rm -rf`, `drop table`, `curl \| bash`; `PostToolUse` log mọi Bash command; `ConfigChange` audit settings | [Claude Code hooks](https://code.claude.com/docs/en/hooks-guide), [Lars Roettig](https://larsroettig.me/blog/claude-code-best-practices) |
| **Human-in-the-loop approval** | Chỉ approval cho **irreversible + externally-visible**: gửi tiền, xóa data, email khách, post công khai, đổi production. Approval classifier = deterministic logic, không phải LLM; tier theo risk; audit mọi approval. ⚠️ **Approval fatigue**: user auto-approve ~93% prompts → containment (sandbox) thắng supervision | [Taskade](https://www.taskade.com/blog/ai-guardrails), [OpenAI HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/), [AWS Agentic AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentsec04-bp02.html), [Anthropic how-we-contain-claude](https://www.anthropic.com/engineering/how-we-contain-claude) |
| **Sandbox / isolation** | OS-level sandbox (Seatbelt/bubblewrap): reads allowed, writes inside workspace, network denied → **giảm 84% permission prompts**; "If credentials never enter the sandbox, they can't be exfiltrated"; controls nằm NGOÀI model control plane | [How we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude), [Codex sandboxing](https://developers.openai.com/codex/concepts/sandboxing), [NVIDIA](https://developer.nvidia.com/blog/four-ways-to-deploy-more-secure-ai-agents/) |
| **Giới hạn: max steps / budget / timeout** | MaxSteps (tool-execution cap), LoopLimit (phát hiện lặp — default 3), ApproveTool (pre-action gate), rate limiting, circuit breakers | [Go Micro agent guardrails](https://go-micro.dev/docs/guides/agent-guardrails.html), [AWS temporal policies](https://aws.amazon.com/about-aws/whats-new/2026/08/temporal-policies-agentcore/) |
| **Observability / audit** | Telemetry agent-native: vì SAO agent hành động (original request, tool calls, approval decisions), không chỉ WHAT; OpenTelemetry export; immutable audit log tách khỏi git history | [OpenAI running-codex-safely](https://openai.com/index/running-codex-safely/), [Okta](https://www.okta.com/identity-101/how-to-implement-least-privilege-for-ai-agents/), [Anthropic](https://www.anthropic.com/news/our-framework-for-developing-safe-and-trustworthy-agents) |
| **Kill-switch / rollback** | Dừng/redirect bất cứ lúc nào; `/rewind`; checkpoints; approval timeout + escalation path (block safe-fallback); rollback = merge-gate requirement | [Anthropic framework](https://www.anthropic.com/news/our-framework-for-developing-safe-and-trustworthy-agents), [AWS Agentic AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentsec04-bp02.html) |

### 3.3 Quy tắc agentic-coding cụ thể (bỏ vào CLAUDE.md/rules của project)

1. **Plan-first**: plan mode (read-only) → produce plan → human approve → implement → verify với plan. "Letting Claude jump straight to coding can produce code that solves the wrong problem." ([Claude Code best practices](https://code.claude.com/docs/en/best-practices), [Netguru](https://www.netguru.com/blog/agentic-development-production-grade))
2. **Không commit/push khi chưa được yêu cầu** — "The agent never merges and never deploys. Humans hold both ends of the loop, the intent and the merge." ([AgenticRepoTemplate](https://github.com/BenSheridanEdwards/AgenticRepoTemplate))
3. **Không dependency mới / API call ngoài khi chưa duyệt**; atomic commits; migration forward-diff only. (Netguru)
4. **Không lệnh destructive** — `rm -rf`, force-push, prod deploy → PreToolUse block. (Claude Code hooks, [Lars Roettig](https://larsroettig.me/blog/claude-code-best-practices))
5. **Test trước merge** — "Never give an agent a task without a failing test. The test defines 'done'"; test-count guard (agent không được xóa test để qua CI). ([GitLab playbook](https://handbook.gitlab.com/handbook/engineering/workflow/ai-assisted-development/), [AgentPatterns](https://agentpatterns.ai/code-review/reviewers-playbook-agent-authored-prs/))
6. **Scope discipline** — "Allowed files vs actual files changed"; no drive-by refactors với functional changes; PR chạm >5 files không liên quan = flag. ([Spec Coding](https://spec-coding.dev/ai-coding-pr-review-checklist), [Konuke](https://konuke.com/blog/pr-review-checklist-for-agent-assisted-code))
7. **Evidence-based done** — agent summary là "claims until commands/tests/logs/diff chứng minh"; executable standards (hooks, CI gates) > written standards. ([Spec Coding](https://spec-coding.dev/ai-coding-pr-review-checklist), [pvgomes](https://pvgomes.com/2026/07/14/review-and-verification-for-agent-code/))
8. **Adversarial review subagent** — review diff trong context tươi (chỉ thấy diff + criteria, không thấy reasoning của writer). (Claude Code best practices)
9. **Environment separation** — "Never write to the production database from tests" là canonical hard constraint; dev/staging/prod tách biệt. ([Claude Code CLAUDE.md guidance](https://support.claude.com/en/articles/14553240-give-claude-context-claude-md-and-better-prompts))
10. **Definition of done có thể máy check** — "Done means the gates are green and the proof is present, and at no other time". ([AgenticRepoTemplate](https://github.com/BenSheridanEdwards/AgenticRepoTemplate))

> **Lưu ý quan trọng từ Anthropic**: approval fatigue là có thật (93% prompts được auto-approve, càng nhiều approval càng ít chú ý) → **containment (sandbox + hooks hard-block) mạnh hơn supervision** ([how-we-contain-claude](https://www.anthropic.com/engineering/how-we-contain-claude)). → Đừng chỉ dựa vào "hỏi user", hãy hard-block bằng hooks.

---

## Phần 4. MLOps/LLMOps — đẩy lên theo sprint

### 4.1 Pipeline CI/CD chuẩn ("Evals are CI")

```
lint → unit tests → golden-set eval (fast subset) → regression vs baseline → build → deploy (canary/shadow) → online monitoring
```

- **Golden set chạy trong CI, block merge khi score tụt** — "Every prompt or model change runs against it, and the job fails if any tracked metric regresses past a threshold." ([DevOpsNess](https://www.devopsness.com/blog/shadow-testing-and-canary-releases-for-llm-changes), [prodinit](https://prodinit.com/blog/llmops-guide-2026))
- **RAGAS có mode CI**: `evaluate(..., in_ci=True)` reproducibility; `@pytest.mark.ragas_ci`; assert `faithfulness >= 0.9` etc. ([RAGAS docs](https://docs.ragas.io/en/latest/howtos/applications/add_to_ci/))
- **Split suite cho tốc độ**: PR gate = faithfulness + answer relevancy (cheap, reference-free) trên subset; full 4-metric suite chạy nightly. **Nếu CI eval > ~15 phút, engineer bắt đầu skip** *(đơn nguồn)*. ([Alok Daftuar](https://aloknecessary.github.io/blogs/llm-evaluation-in-production/), [QASkills](https://qaskills.sh/blog/ragas-llm-evaluation-guide))
- **Threshold từ baseline, không phải wishful thinking** — chạy trên main branch hiện tại, set floor dưới một chút để regression thật trip gate còn noise thì không. ([QASkills](https://qaskills.sh/blog/ragas-faithfulness-answer-relevancy-guide))
- **Track phân phối (P50/P90/P99), không chỉ mean** — "average faithfulness 0.90 giấu 10% query ở 0.30". ([niteagent](https://niteagent.com/blog/2026-06-12-rag-evaluation-pipeline-guide/))
- **⚠️ Legal caveat**: cả 3 framework đều dùng LLM-as-judge, "không phân biệt được context sai trong domain chuyên sâu (luật nêu rõ)" → **domain calibration bắt buộc trước khi tin điểm số**. Judge nên khác model family với generator. ([particula.tech](https://particula.tech/blog/deepeval-vs-ragas-vs-trulens-rag-evaluation-stack), [tianpan.co](https://tianpan.co/blog/2026-05-04-continuous-production-eval-statistical-quality-monitoring-llm-traffic))

### 4.2 Deployment theo sprint (canary + blue-green)

- **Blue-green "close to mandatory" cho AI** — "model updates can degrade in ways that throw zero errors"; baking period 30min-4h. ([MLflow](https://mlflow.org/articles/what-is-blue-green-ai-deployment/))
- **Canary = dimmer (1→5→25→100%) + auto-rollback watcher**; shadow soak 2-4 ngày; **human quyết định ramp up, threshold quyết định ramp down**. Auto-rollback thresholds mẫu: `faithfulness < baseline - 0.03`, `thumbs_down_rate > 1.25x`, `p95_latency > 1.3x`, `error_rate > +0.005`, `cost_per_req > 1.2x`. ([DevOpsNess](https://www.devopsness.com/blog/shadow-testing-and-canary-releases-for-llm-changes))
- **Prompt edits = production deployments** — route 1%→5%→20%→100%; regression set 50-200 queries với expected output *properties* (not exact outputs) scored by LLM judge ([tianpan.co](https://tianpan.co/blog/2026-04-16-prompt-canary-deployments))
- **Release unit = bundle** (code + prompt + model version + retrieval index + tools); tag mọi run với bundle id; quarantine 24-72h sau cutover ([gravity.fast](https://gravity.fast/blog/ai-agent-blue-green-deployment/))
- **Versioning**: prompt registry + model registry; **pin dated model versions** (`gpt-4o-2024-11-20`) vì provider silently update models; active model trong live config store để swap <30s không cần deploy ([letsbuildsolutions](https://letsbuildsolutions.com/blog/devops/production-readiness-for-ai-applications-model-versioning-inference-monitoring-and-rollback-strategies/))
- **Feature flags chứa prompt version ID, không phải prompt text**; deterministic bucketing (cùng user → cùng variant); coordinated multi-flag rollback (rollback model mà không rollback prompt có thể tệ hơn) ([tianpan.co](https://tianpan.co/blog/2026-04-09-feature-flags-progressive-delivery-llm-features))

### 4.3 Monitoring production (online eval)

- **Async + sampled 1-5% + stratified** (oversample high-stakes query + prompt version mới); judge rẻ (Haiku) calibrate với judge mạnh trên ~50 mẫu, correlation >0.85 → bank savings ([respan](https://www.respan.ai/articles/rag-observability), [alok](https://aloknecessary.github.io/blogs/llm-evaluation-in-production/))
- **7 metrics**: p50/p99 latency (mean là lời nói dối), cost/call ($), **cost/session** (detect runaway agent), cache hit rate, faithfulness, error rate, traffic volume. 5 alerts: latency p99 3x baseline, cost/session 3x outlier, error >1%, **faithfulness floor 7-day rolling 0.90 general / 0.96 regulated (legal)**, traffic ±50% ([respan](https://www.respan.ai/articles/llm-monitoring))
- **Hallucination proxies legal**: citation coverage (giảm = signal sớm), thumbs-down feed thẳng vào golden set, escalation rate ([sphereinc](https://www.sphereinc.com/blogs/rag-pipeline-monitoring))
- **Drift 4 tầng**: structural (100% traffic, rẻ) → behavioral (5-10%) → uncertainty → LLM-judge (1-5%); X-bar control charts (3σ) phát hiện shift đột ngột; **CUSUM** phát hiện drift nhỏ kéo dài; SLO burn-rate alerting ([tianpan.co](https://tianpan.co/blog/2026-05-04-continuous-production-eval-statistical-quality-monitoring-llm-traffic))
- **Embedding drift** (critical cho 6 tháng update): anchor similarity (cùng text không còn embed gần baseline = provider đổi model), neighbor order (top-k đảo = chunking/index rebuild), query coverage (golden recall giảm = content bị xóa) ([qaskills](https://qaskills.sh/blog/embedding-drift-monitoring-tests-guide))

### 4.4 Tooling

| Tool | Loại | License | Vai trò trong stack này |
|---|---|---|---|
| **RAGAS** | Eval framework | Apache-2.0 | ✅ Golden-set eval trong CI (đã có trong plan) |
| **DeepEval** | Eval framework | Apache-2.0 | Pytest-native, thay thế RAGAS nếu muốn |
| **Langfuse** | Observability | MIT, self-host | ✅ Traces + cost + prompt mgmt; chạy trên Postgres riêng |
| **Arize Phoenix** | Observability/drift | Apache-2.0/source-available | Embedding drift detection mạnh nhất |
| TruLens | Observability | MIT | Production tracing (Snowflake) |
| LangSmith | Observability | Proprietary | LangChain shops |

Khuyến nghị hội tụ: **RAGAS trong CI + Langfuse self-host (traces/cost) + Phoenix (drift)** — tất cả OSS, self-host được, data residency tốt. ([aitechconnect](https://aitechconnect.in/news/production-rag-observability-langfuse-langsmith-arize), [datarekha](https://datarekha.com/blog/agent-observability-stack/))

### 4.5 ⚠️ 6 tháng update 1 lần — "Eval Invalidation Paradox" (quan trọng nhất)

> **"Ngay khi bạn update knowledge base, eval set bạn build trên index cũ lặng lẽ ngừng đo thứ nó được thiết kế để đo."**
> Sau ~6 tháng incremental, eval set 50 query có thể đang test corpus mới 40%; score tụt **mà không có model regression**. ([tianpan.co](https://tianpan.co/blog/2026-05-07-rag-eval-invalidation-corpus-update-paradox))

**Hành động bắt buộc:**
1. **Version golden set cùng corpus** — `golden_set_v2.json` sau mỗi update 6 tháng; track dataset version trong eval history. Score tụt sau dataset expansion = expected, không phải regression alert. ([alok](https://aloknecessary.github.io/blogs/llm-evaluation-in-production/), [niteagent](https://niteagent.com/blog/2026-06-12-rag-evaluation-pipeline-guide/))
2. **Re-baseline sau mỗi update** — chạy golden set TRƯỚC (baseline) và SAU update; so sánh delta; quyết định: corpus change (re-baseline) vs real regression (fix). ([tianpan.co](https://tianpan.co/blog/2026-04-27-embedding-migrations-new-schema-migrations))
3. **Đổi embedding/reranker = schema migration, không phải batch job** — parallel index + dual-write + shadow queries (replay prod queries, so top-k overlap + citation success) + rollout theo cohort (query intent) + giữ old index writable 1-4 tuần. **pgvector gotcha: dims baked vào index type, không ALTER được column — phải rebuild index (hours, read-only table)** → parallel-index pattern tránh được. ([tianpan.co](https://tianpan.co/blog/2026-04-27-embedding-migrations-new-schema-migrations), [DevOpsNess](https://www.devopsness.com/blog/embedding-model-upgrades-without-search-chaos-a-safer-rag-rollout-pattern-2026-03-22), [AmtocSoft](https://amtocsoft.blogspot.com/2026/05/embedding-model-migration-in-production.html))
4. **Backup trước update + rollback = routing/flag flip, không phải redeploy**; keep previous index alive 1-4 tuần; reindex idempotent + resumable (deterministic idempotency keys + `text_hash` column). ([AmtocSoft](https://amtocsoft.blogspot.com/2026/05/embedding-model-migration-in-production.html), [sysart](https://sysart.consulting/insights/embedding-model-lifecycle-on-premises-rag/))

> **GAP**: chưa có nguồn phổ dụng cho "X% drop = fail CI" — mọi nguồn đều calibrate theo baseline riêng. Số 2% recall@10 (AmtocSoft, corpus pháp lý 38M đoạn — relevant nhưng single-source) và 0.05 delta reference-free (Alok) là điểm khởi đầu tốt.

---

## Phần 5. Dịch vụ deploy uy tín tại Đà Nẵng

### 5.1 So sánh (đầy đủ)

| Nhà cung cấp | DC tại Đà Nẵng | Managed PG | Giá tham chiếu (~/tháng) | Ưu | Nhược |
|---|---|---|---|---|---|
| **Viettel Cloud** ⭐ | ✅ **Có** (Software Park, 02 Quang Trung, Hải Châu) | ✅ vDBS (PG 12/15) | VPS 2vCPU/4GB ≈235k; vDBS từ 450k | Lớn nhất VN, uy tín nhà nước, DC + managed PG tại Đà Nẵng, rẻ | Giá quote-based, console kém dev-friendly, PG max 15 |
| **VNPT Cloud** | ✅ An Đồn DC (Sơn Trà) | ✅ Cloud Database | SMC05 4/8 ≈759k | ISP #1, 8 DC Tier III, unlimited bandwidth | Đắt hơn Viettel 50-90%, console kém |
| **FPT Cloud** | ⚠️ FPT City Đà Nẵng (chưa verify) | ✅ PG 11-17, 30 ngày free trial | 4vCPU/8GB ≈1.3M+ | PG versions hiện đại nhất, auto-scaling | Giá mờ (quote), định vị cao cấp |
| **CMC Cloud** | ❌ Không (HN + HCM) | Có | 8vCPU/16GB ≈3.8M | Security mạnh (PCI DSS đầu VN), DDoS tốt | Đắt, overkill; nhánh Đà Nẵng chỉ bán lẻ lại |
| **Bizfly (VCCorp)** | ❌ Không (HN + HCM) | Có | Micro ≈117k → Large ≈945k | Giá công khai, dev-friendly, K8s | Review cộng đồng chê giá cao |
| **PowerNet** (local ĐN) | ✅ **Tại VNPT An Đồn DC** | ❌ (tự quản) | 2vCPU/4GB/50GB ≈292k-456k | Rẻ nhất, physical proximity, support tiếng Việt | Công ty nhỏ (rủi ro uy tín), single DC, no managed PG |
| **AWS Singapore** | ❌ (35-60ms từ ĐN) | ✅ RDS | 2.5M-5M+ | Full managed, PG hiện đại | ~2x giá, không data residency VN |

Nguồn: [Viettel vDBS](https://viettel-cloud.com.vn/viettel-database-service-en/), [Viettel IDC](https://viettel-idc.com.vn/index.php/dich-vu/viettel-data-center-consulting.html), [Viettel Danang DC colomap](https://colomap.com/facilities/viettel-danang-dc/), [FPT pricing](https://fptcloud.com/en/pricing/), [FPT PG versions](https://docs.fptcloud.com/docs/fpt-database-engine/managed-fpt-database-engines-new/concepts/database-engine-version/Version-List/), [VNPT Cloud](https://cloud.vnpt.vn/), [PowerNet](https://powernet.vn/vps-viet-nam.php), [Bizfly pricing](https://bizflycloud.vn/cloud-server/bang-gia)

### 5.2 Khuyến nghị

**→ Viettel Cloud là lựa chọn số 1** — duy nhất thỏa cả 3 yêu cầu cứng: (1) có mặt vật lý tại Đà Nẵng, (2) managed PostgreSQL, (3) độ tin cậy quốc gia. Chi phí ước tính ~700k-1.7M VND/tháng.

**Nếu budget hẹp cho MVP**: tự quản PG trên VPS Viettel (4vCPU/4GB/60GB ≈315k) — vì project vốn chạy PG cùng box (PGTableGraphStorage), premium managed-DB có thể hoãn. Blob: PowerNet ≈300k/tháng cho test latency vs cost.

**Tránh** cho workload này: CMC (đắt/overkill), MISA (không phải host), PikaMC (game server), AWS làm primary (trừ khi cần data residency nước ngoài hoặc PG >15).

> ⚠️ **Lưu ý**: toàn bộ bảng giá VNPT/Viettel/FPT từ AI-synthesized response (single source) — chỉ là leads, bắt buộc verify bằng quote vendor trước khi quyết định. Giá VN biến động.

---

## Phần 6. Khuyến nghị tích hợp vào dự án rag-real-estate (actionable)

### A. Security (Phần 1) — bổ sung vào ADR/rules
1. **Thêm lớp chống injection 4 lớp**: Llama Prompt Guard 2 (86M hoặc 22M) screen input + retrieved chunks trong FastAPI; delimiters/JSON-encode cho retrieved content; instruction-hierarchy system prompt; output screening. *Test tiếng Việt FPs/FNs TRƯỚC khi tin classifier (Azure/Guard đều chưa verify VN).*
2. **Mở rộng post-retrieval filter hiện có** (rule 7: effective_date/status) → thêm injection screening + access-control check tại retrieval-time.
3. **Ingestion governance**: SHA-256 hash + provenance + scan invisible Unicode + allowlist nguồn.
4. **Giữ `max_total_tokens` 8-12k** — cũng là giới hạn blast radius của injection.
5. **Red-teaming định kỳ** với OWASP injection corpus.

### B. Document roles (Phần 2) — bổ sung vào kiến trúc
1. **Tạo state machine `documents`** (draft → review → approved → published → deprecated → deleted); chỉ `published` vào index. → **Đây là "roles quản lý tài liệu" bạn đang thiếu.**
2. **Role model**: admin / document manager / SME reviewer / legal approver / viewer / auditor; **uploader ≠ approver (SSD)**.
3. **PG RLS trên chunk table** (PGTableGraphStorage/PGVector là plain PG): `FORCE RLS`, runtime role `NOBYPASSRLS`, `SET LOCAL` identity, canary-tenant tests. Metadata ACL (roles, classification, effective_date, status, source_id, version) dán lên TỪNG chunk lúc ingest.
4. **Cascade delete** khi deactivate doc; audit log replayable.

### C. AI-Engineering rules (Phần 3) — bổ sung vào `.claude/` project
1. **Hooks (PreToolUse) hard-block**: `.env`, `drop table`, `rm -rf`, `curl | bash`, git push, prod deploy.
2. **CLAUDE.md project**: quy tắc plan-first, không commit khi chưa hỏi, test trước merge, scope discipline, kèm số liệu (93% approval fatigue → ưu tiên containment).
3. **Permission settings check-in git**; sandbox cho unattended runs.

### D. MLOps (Phần 4) — bổ sung vào scripts/
1. **CI gate**: PR = faithfulness + answer relevancy subset; nightly = full 4 metric; block merge khi regression >0.05 (or 2% recall@10 legal).
2. **Version golden set cùng corpus** — `eval/golden_set_v2.json` sau mỗi update 6 tháng; re-baseline.
3. **Deploy sprint**: shadow → canary 5% → 25% → 100% + auto-rollback watcher; blue-green standby 24-72h; pin dated model versions; bundle id trong trace.
4. **Monitoring**: Langfuse self-host + Phoenix drift; faithfulness floor 0.96 (regulated); citation coverage alert.
5. **Update 6 tháng**: backup → parallel index nếu đổi embedding → incremental ingest → regression before/after → re-baseline.

### E. Deploy (Phần 5)
- **Mile 1 (MVP pilot)**: Viettel Cloud VPS tự quản PG (hoặc PowerNet nếu budget tối thiểu) → đặt ở DC Đà Nẵng cho latency <5ms với user Đà Nẵng.
- **Mile 2 (production)**: Viettel vDBS managed PG + VPS; cân nhắc FPT nếu cần PG 16/17.
- **Kế hoạch dự phòng**: CMC/Cloudflare cho DDoS; giữ runbook rollback.

---

## Sources chính (đầy đủ xem trong từng phần)

1. [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html) — chuẩn bảo mật RAG
2. [OWASP GenAI LLM01 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) — LLM Top 10
3. [Microsoft: How Microsoft defends against indirect prompt injection](https://www.microsoft.com/en-us/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks) — spotlighting, HITL
4. [Anthropic: Mitigate jailbreaks and prompt injections](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks) — pre-screen, JSON-encode
5. [Instruction Hierarchy (Anthropic)](https://arxiv.org/html/2404.13208) — paper
6. [Meta Llama Prompt Guard 2](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M) — classifier 19.3ms
7. [Azure Prompt Shields](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection)
8. [AWS Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html) — contextual grounding
9. [NVIDIA NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)
10. [Guardrails AI docs](https://www.guardrailsai.com/docs)
11. [NIST RBAC](https://csrc.nist.gov/projects/role-based-access-control) + [ANSI INCITS 359-2004](https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/ANSI+INCITS+359-2004.pdf)
12. [knowledge-base.software governance framework](https://knowledge-base.software/guides/knowledge-base-governance-framework/)
13. [kawshik.dev: multi-tenant RAG pgvector RLS](https://kawshik.dev/blog/multi-tenant-rag-pgvector-postgres-rls.html) — hardening chi tiết
14. [PostgreSQL RLS docs](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
15. [Supabase: RAG with permissions](https://supabase.com/docs/guides/ai/rag-with-permissions)
16. [AWS: Authorizing access with RAG](https://aws.amazon.com/blogs/security/authorizing-access-to-data-with-rag-implementations/)
17. [Pinecone: RAG access control](https://www.pinecone.io/learn/rag-access-control/)
18. [Anthropic: Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
19. [Anthropic: How we contain Claude](https://www.anthropic.com/engineering/how-we-contain-claude) — 93% approval fatigue, sandbox 84%
20. [Claude Code hooks guide](https://code.claude.com/docs/en/hooks-guide) — "hooks are law"
21. [Claude Code permissions](https://code.claude.com/docs/en/permissions)
22. [OpenAI: A practical guide to building agents](https://openai.com/index/a-practical-guide-to-building-agents/)
23. [OpenAI: Running Codex safely](https://openai.com/index/running-codex-safely/)
24. [Netguru: Agentic Development Production-Grade](https://www.netguru.com/blog/agentic-development-production-grade)
25. [RAGAS: eval in CI](https://docs.ragas.io/en/latest/howtos/applications/add_to_ci/)
26. [DevOpsNess: shadow testing + canary for LLM](https://www.devopsness.com/blog/shadow-testing-and-canary-releases-for-llm-changes) — auto-rollback thresholds
27. [tianpan.co: RAG eval invalidation paradox](https://tianpan.co/blog/2026-05-07-rag-eval-invalidation-corpus-update-paradox)
28. [tianpan.co: embedding migrations](https://tianpan.co/blog/2026-04-27-embedding-migrations-new-schema-migrations)
29. [MLflow: blue-green AI deployment](https://mlflow.org/articles/what-is-blue-green-ai-deployment/)
30. [respan: LLM monitoring metrics](https://www.respan.ai/articles/llm-monitoring) — faithfulness floor 0.96 regulated
31. [Viettel vDBS managed DB](https://viettel-cloud.com.vn/viettel-database-service-en/) — PG 12/15, từ 450k
32. [Viettel Danang DC colomap](https://colomap.com/facilities/viettel-danang-dc/) — 02 Quang Trung, Hải Châu
33. [FPT Cloud pricing](https://fptcloud.com/en/pricing/) + [FPT PG versions](https://docs.fptcloud.com/docs/fpt-database-engine/managed-fpt-database-engines-new/concepts/database-engine-version/Version-List/)
34. [VNPT Cloud](https://cloud.vnpt.vn/)
35. [PowerNet VPS](https://powernet.vn/vps-viet-nam.php) — local Đà Nẵng tại VNPT An Đồn
36. [Bizfly Cloud pricing](https://bizflycloud.vn/cloud-server/bang-gia)

---

## Methodology

- 5 subagents research song song (RAG security / document roles / AI-engineering rules / MLOps / Đà Nẵng services)
- ~25+ search queries (WebSearch + Exa + aibox), deep-read 15-20 nguồn chính
- Mọi claim đều có nguồn; số liệu single-source được đánh dấu; giá VN đánh dấu "estimate, verify vendor"
- GAP đã nêu: (a) classifier injection chưa test tiếng Việt, (b) chưa có chuẩn confidence 3-tier legal,
  (c) chưa có số universal "X% drop = fail CI", (d) giá VPS VN từ AI-synth cần quote vendor
