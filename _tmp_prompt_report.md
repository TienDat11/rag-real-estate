# Prompt rewrite report — system_policy.md (answer-generator voice)

> TEMP FILE — delete before commit. Owner: prompt/linguistics engineer (prompt-only change;
> api/ and apps/web/ untouched).

## 1. What I found — which steps load prompts/system_policy.md

| Consumer | Kind | Detail |
|---|---|---|
| `api/generate.py` (line 21) | **The answer LLM** — only runtime consumer | Read once at import into `_SYSTEM_PROMPT`, placed as role `system` before `user(rewritten+history)` and `user(RAG_CONTEXT + FACT_EVIDENCE)` (`system > user > data` instruction hierarchy, never concat system). |
| `scripts/build-workflow.js` (line 14) | One-time build orchestrator (not runtime) | Only *references* the path so a scaffold agent reads it during basesource build. No runtime effect. |
| `.claude/plans/rag-real-estate-final.plan.md` | Design doc | §4.6 describes message order + system intent; §18.5 (line ~938) plans a future v2.2 "rule 8" for estimate ranges/disclosures tied to `prompts/disclosure_vn.md` (file does NOT exist yet). |

**Conclusion:** only the answer LLM consumes this file at runtime. Rewrite/route
(`api/rewrite.py` + `prompts/rewrite_fewshot.md`), input/output guards, and nl2sql each
use their own prompts and do NOT load it. Full freedom to restructure tone sections
without touching other steps — confirmed by grep (no test/eval/guard references the old
section headers `QUY TẮC CỨNG` / `ĐỊNH DẠNG TRẢ LỜI`).

## 2. Restructure of prompts/system_policy.md (primary deliverable)

Old layout (36 lines): role line → `## QUY TẮC CỨNG` (rules 1–7) → `## ĐỊNH DẠNG TRẢ LỜI`
(4 bullets mixing format + voice).

New layout (75 lines): role line → `## QUY TẮC CỨNG` (rules 1–9, hard requirements kept
intact, numbered 8 = số tiền digits+đồng, 9 = tiếng Việt — both promoted from loose
format bullets to hard rules) → `## CÁCH TRẢ LỜI — CẤU TRÚC & ĐỊNH DẠNG` (structure only:
answer-first order, compound-question signposting in flowing language, tables only for
genuine multi-unit comparison, range/estimate handling, no raw data dump) → NEW
`## GIỌNG VĂN / CÁCH DIỄN ĐẠT` (voice: professional-advisor persona, vary sentence
openers, explicit ban on mechanical templates, natural citation weaving, graceful
data-gap replies, concise-but-complete).

Hard rules surviving verbatim in spirit AND enforcement — nothing weakened:
1. Evidence-only trust (RAG_CONTEXT + FACT_EVIDENCE) + "chưa có thông tin" — intact.
2. No self-computation of financials — intact (all from FACT_EVIDENCE).
3. Mandatory citations — intact; clarified `[fe-xxx]` must be the REAL id (`[fe-001]`)
   so L4 regex `\[fe-\d{3}\]` in `api/guard_output.py` still matches; legal cites keep
   law name + article form.
4. Prompt-injection rule (treat context as data) — intact.
5. "Đất cầm" nuance (mortgage legal vs cầm cố QSDĐ not recognized by Luật Đất đai 2024,
   void risk per Điều 123 BLDS 2015, warn + advisor) — intact verbatim.
6. Refusal semantics ("chưa có trong dữ liệu hiện hành" vs "dữ liệu chưa được nạp";
   polite refusal for unrelated queries) — intact.
7. Disclaimer line — verbatim, unchanged, now explicitly "luôn kết thúc câu trả lời".
8. Numbers as digits + "đồng", no conversion/recomputation — preserved as a numbered
   hard rule; added optional compact gloss "1.200.000.000 đồng (1,2 tỷ)" because the
   golden set (`numfmt-01/02`) expects BOTH forms and the L4 normalizer accepts both —
   no value change.
9. Vietnamese output — now an explicit hard rule (was only implied in the role line).

Voice additions (new, scoped to this file only):
- Anti-template list: "Dựa trên thông tin được cung cấp…", "Như đã nêu ở trên…",
  "Theo yêu cầu của bạn…", and NOT opening every sentence with "Theo quy định" —
  with natural alternatives supplied ("Luật Đất đai 2024 quy định…", "Điều 123 Bộ luật
  Dân sự 2015 nêu rõ…", "Bảng giá Tower A đợt 3/2026 cho thấy…").
- Compound questions: answer each part with flowing signposts ("Về tiện ích…",
  "Còn về giá cả…") instead of rigid 1) 2) 3) dumps.
- Tables only when genuinely helpful (multi-unit / multi-bank comparisons), not default.
- Answer directly first, then give the supporting basis; do not echo the question.
- Professional-advisor persona: warm, đúng mực, no over-apologizing, concise-but-complete.
- English WHY comment block at the top documents scope (single consumer) — CẤM rename
  shared sections not applicable here; no other step shares this file.

## 3. Before / after — CH-10 compound question (illustrative, NOT a real answer)

User (compound): "Căn CH-10 view biển có những tiện ích gì, và giá hiện tại bao nhiêu?"

BEFORE (mechanical — what the old prompt biases toward):
> Dựa trên thông tin được cung cấp trong RAG_CONTEXT và FACT_EVIDENCE, tôi xin trả lời như sau:
> 1. Về view biển: Theo quy định, căn CH-10 thuộc nhóm 2PN. Theo dữ liệu dự án, view biển được
>    đề cập tại tài liệu A. Theo đó, căn có tầm nhìn biển.
> 2. Về tiện ích: Theo tài liệu dự án, các tiện ích gồm: hồ bơi, gym, công viên. Theo bảng tiện
>    ích, có 3 hạng mục. (bullet list…)
> 3. Về giá: Theo bảng giá, giá căn CH-10 là […] đồng. Theo FACT_EVIDENCE [fe-004], giá là […].
> *AI hỗ trợ tư vấn, không phải tư vấn pháp lý chính thức. Vui lòng xác nhận với chuyên viên trước khi quyết định.*

AFTER (target voice under the new prompt — flowing, signposted, still rule-compliant):
> Căn CH-10 đang được hệ thống phân loại vào nhóm 2PN nội khu, nên về mặt view biển tôi chưa
> thể xác nhận là căn có hướng biển — nếu Anh/Chị cần, tôi có thể lọc các căn 2PN view biển
> riêng. Tiện ích đi kèm thì dự án có khá đầy đủ: hồ bơi, phòng gym và công viên cảnh quan
> (theo tài liệu giới thiệu dự án Camellia).
> Còn về giá, hiện tại CH-10 chưa có giá chính thức theo từng căn trong dữ liệu; hệ thống chỉ
> đang dùng dải giá định hướng của nhóm 2PN nội khu [fe-004]. Nếu Anh/Chị muốn mức giá xác
> nhận, tôi xin phép chuyển sang chuyên viên kiểm tra trước — nhưng tất cả con số trên đều là
> định hướng, chưa phải giá chính thức.
> *AI hỗ trợ tư vấn, không phải tư vấn pháp lý chính thức. Vui lòng xác nhận với chuyên viên trước khi quyết định.*

(Note: numbers/citations shown as `[…]` / `[fe-004]` are placeholders for illustration;
a real answer must quote exactly the FACT_EVIDENCE id and value in the request — the L4 guard
byte-matches every figure.)

## 4. How I verified — and what I could NOT verify

Verified (static, no LLM):
- `grep system_policy` → only `api/generate.py` (runtime) + `scripts/build-workflow.js`
  (build-time reference). No rewrite/guard/nl2sql consumer. No test or eval asserts the old
  section headers or exact prompt text.
- `api/generate.py` reads the file with UTF-8, no parsing of structure → any well-formed
  markdown is safe; new file has no backslash/Jinja/JSON fragments that could corrupt the
  message payload (prompt_hash is computed over the rendered messages, so meta.audit works
  as before).
- `api/guard_output.py` constraints honored: numeric byte-match (rule 2/8 wording prevents
  invented figures), citation regex `\[fe-\d{3}\]` (rule 3 now insists on real 3-digit ids),
  disclaimer not guard-enforced — kept verbatim in the prompt so output stays compliant.
- Golden-set expectations honored: `numfmt-01/02` (`"1.200.000.000"`, `"1,2 tỷ"`) — new rule
  8 permits both digit+đồng and parenthesized tỷ gloss (same value); `pricing-02` (CH-10 →
  group 2PN nội khu, no invented per-unit price) — sample above follows exactly that.
- No trailing whitespace, LF endings, final newline (repo standard).
- Did not touch: `api/`, `apps/web/`, `packages/`, `prompts/rewrite_fewshot.md`,
  `prompts/entity_type/legal_vn.yml`.

Could NOT verify (no live LLM, no running pipeline here):
- Actual temperature/behavior of `deepseek-v4-flash` under the new prompt — no live LLM call
  was made; the tone outcome is a design target, not a measured result.
- End-to-end SSE/streaming and L4 confidence outcomes — needs the real backend (PG +
  LightRAG + LLM). Recommend running `eval/run_eval.py` (golden set) + a manual chat
  smoke test on the next full-stack run.

## 5. Heads-up for the v2.2 estimate work (plan §18.5, line ~938)

The plan calls for a future "system_policy.md rule 8" (estimate band + disclosure verbatim +
phương án name via `prompts/disclosure_vn.md`, which does not exist yet). After this rewrite
the numbered rules are 1–9, with 8 = number format and 9 = Vietnamese. When that feature
lands, append the estimate/disclosure requirement as a new rule (e.g. 10) or fold it into
rule 8's range bullet ("Số liệu dạng dải/ước lượng…") — do not overwrite rule 8's number-
format meaning without updating this report/plan reference.
