You are a senior frontend designer/engineer working in the monorepo at D:\rag-real-estate. You own ONLY apps/web/ (Next.js 16 + React 19 + antd v5 + Tailwind v4). The web app is a Vietnamese legal/real-estate RAG chat assistant. The user (Vietnamese-speaking, professional) says the current UI "looks 100% AI-generated, not serious at all — I will not read it", and wants loading progress shown to the customer while the backend works.

FIRST ACTION: load these skills via the skill tool (exact names): "design-taste-frontend", "imagegen-frontend-web", "frontend-design-direction", "accessibility", "frontend-a11y". Apply them (this is a product tool, not a landing page — per frontend-design-direction, design for repeated daily use: dense, quiet, scannable, professional; avoid marketing-page compositions).

## Important repo facts
- Read D:\rag-real-estate\apps\web\AGENTS.md / CLAUDE.md first: this is Next.js 16 with breaking changes; read node_modules/next/dist/docs/ (relative to apps/web) before writing code.
- Stack is already locked: next 16.3.0, react 19.2.8, antd ^5.22.0 + @ant-design/icons ^5.5.1, @ant-design/v5-patch-for-react-19, react-markdown ^9 + remark-gfm ^4, tailwindcss ^4 (@tailwindcss/postcss). Do NOT add new deps unless clearly necessary; if you do, justify and ensure they are react-19 compatible.
- Files you own (under apps/web/src): app/layout.tsx, app/page.tsx, components/ChatPage.tsx, components/MessageBubble.tsx, components/MessageList.tsx, components/EvidencePanel.tsx, components/Composer.tsx, lib/api.ts, lib/constants.ts, plus globals.css if present.
- packages/@rag-ragre/contracts and packages/@rag-ragre/ui are consumed from dist/ — you do NOT need to rebuild them unless you edit packages/, and you should NOT edit packages/ (another concern; keep this PR apps/web-only). You may import types from @rag-ragre/contracts as they already do.
- The existing SSE client (lib/api.ts, streamQuery) dispatches SOURCES/FACTS/TOKEN/DONE/ERROR via handlers. A backend agent is ADDING a new SSE event "progress" with payload {"step": "guard"|"rewrite"|"rag"|"sql"|"geo"|"rerank"|"merge"|"generate"|"done"|"error"} (raw step keys only). You must consume it.

## What to build (knock out both)
### A. Professional redesign (the big one)
The chat UI must look like a serious, carefully designed product for a real estate brokerage/legal consultancy — not a generic AI demo. Goals:
- Clean, confident visual hierarchy; one restrained accent; proper typography scale; consistent radii/spacing; WCAG AA contrast everywhere (a11y skills).
- Improve: ChatPage layout (header/branding, conversation surface), MessageBubble (user vs assistant, citations/evidence, markdown rendering quality, code/table styles), MessageList (empty state, suggestion chips), EvidencePanel (facts + sources presentation — keep the pricing "Bậc giá theo tầng" badge and FactEvidence rendering intact, do not break the story-3.3 pricing work), Composer (input, send button, disabled/loading states, keyboard a11y).
- Empty/loading/error states must be polished (see design skills). Keep it Vietnamese-friendly. Avoid generic AI-purple gradients, centered-everything, three-equal-cards, Inter+slate default, em-dash flourishes, and other anti-patterns from the skill.
- Accessibility: real label or aria-label on the input, visible focus, aria-live for streaming status, semantic buttons (no div-onClick), min 44px targets where practical, prefers-reduced-motion respected.

### B. Loading progress trail (the explicit user requirement)
"Khi đang load, tôi muốn khách hàng thấy tiến trình: bot đang làm gì — suy nghĩ/phân tích, tra cứu tài liệu, tra cứu bản đồ/tiện ích, tra cứu dữ liệu — hiển thị chú thích thân thiện. TUYỆT ĐỐI không hiện id nội bộ, không lộ thông tin nội bộ."
So: while streaming, show a subtle step-by-step indicator under/above the assistant bubble with friendly Vietnamese labels mapped from the raw SSE "progress" step keys, e.g.:
  guard -> "Đang kiểm tra yêu cầu…"
  rewrite -> "Đang phân tích câu hỏi…"
  rag -> "Đang tra cứu hồ sơ pháp lý & tài liệu…"
  sql -> "Đang tra cứu dữ liệu dự án, giá bán…"
  geo -> "Đang tra cứu bản đồ, tiện ích xung quanh…"
  rerank -> "Đang sắp xếp nguồn trả lời…"
  merge -> "Đang tổng hợp thông tin…"
  generate -> "Đang soạn câu trả lời…"
  done -> (hide/complete the trail)
  error -> "Đã xảy ra lỗi khi xử lý câu hỏi."
Rules: NEVER render the raw step key, NEVER show ids/trace ids/model names/environment names; only the friendly text. The mapping table lives in one constants file (e.g. lib/progress.ts). The trail should animate (step transitions), be unobtrusive, respect prefers-reduced-motion, and disappear/replace itself when real tokens start streaming (or collapse into a "Đã xong" state). Add an aria-live="polite" region announcing the current step.
- Add onProgress to lib/api.ts QueryStreamHandlers (handle the new "progress" event; leave existing handlers intact).
- Keep the existing ASK_EVENT suggestion behavior and EvidencePanel onDone wiring intact.

## Verification (must pass before you finish)
- D:\rag-real-estate: npm run typecheck -w @rag-ragre/web
- npm run build -w @rag-ragre/web  (root workspaces; may need npm install at repo root first if node_modules missing — that is allowed, report it)
- Prefer no new eslint errors: npm run lint -w @rag-ragre/web
Note: you cannot see the running app here; there is no browser automation guaranteed. The BE/DB/LLM are not reachable, so the SSE will not stream live in this env — verify by typecheck/build and by carefully reasoning through the streamQuery handler flow; optionally write a tiny node/tsx script that feeds fake SSE frames to a stub if feasible. Do not fabricate "tested in browser" claims; say exactly how you verified.

## Deliverables
1. Summary of the design direction you chose (one paragraph, the "design read").
2. Exact list of files changed in apps/web with descriptions.
3. The friendly-label mapping table as built.
4. How you verified (commands + output tails) and any parts you could not verify here.
5. Write your final report to D:\rag-real-estate\_tmp_ui_report.md (note in it that it should be deleted before commit).

Constraints: English WHY comments only, no banner comments, no em-dashes in user-visible copy (Vietnamese text too), newline at EOF. Do NOT touch api/, prompts/, packages/ or eval/. Do not break the existing pricing FactsTable badge or contracts types.