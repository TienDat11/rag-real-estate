"use client";

/**
 * Loading progress shown to the end user while the answer is being prepared.
 *
 * The backend emits `progress` SSE events with a raw step key
 * ({"step": "rag"}). We map each key to a friendly, customer-facing Vietnamese
 * label — the raw keys, tool names, ids and counts must NEVER reach the UI.
 * `done` hides the trail; `error` is rendered by the existing error state.
 */

export type ProgressStep =
  | "guard"
  | "rewrite"
  | "rag"
  | "sql"
  | "geo"
  | "rerank"
  | "merge"
  | "generate"
  | "done"
  | "error";

/** Friendly labels keyed by backend step name (no internal identifiers). */
export const PROGRESS_LABELS: Record<ProgressStep, string> = {
  guard: "Đang kiểm tra yêu cầu…",
  rewrite: "Đang phân tích câu hỏi…",
  rag: "Đang tra cứu hồ sơ pháp lý & tài liệu…",
  sql: "Đang tra cứu dữ liệu dự án, giá bán…",
  geo: "Đang tra cứu bản đồ, tiện ích xung quanh…",
  rerank: "Đang sắp xếp nguồn trả lời…",
  merge: "Đang tổng hợp thông tin…",
  generate: "Đang soạn câu trả lời…",
  done: "",
  error: "",
};

/** Resolve a raw backend step key to its friendly label (empty if unknown). */
export function friendlyProgressLabel(raw: string): string {
  return PROGRESS_LABELS[raw as ProgressStep] ?? "";
}
