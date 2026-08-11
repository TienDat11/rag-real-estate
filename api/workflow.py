"""Async orchestrator for the 8-step query pipeline (plan §4.0).

Flow: guard -> rewrite/route -> RAG + SQL legs in parallel -> rerank + merge ->
generate (stream) -> output guard -> audit. Every step degrades gracefully on
timeout/error instead of crashing the pipeline.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Awaitable

from api import sha256_hex
from api.audit import write_audit
from api.constants import (
    SSE_EVENT_FACTS,
    SSE_EVENT_SOURCES,
    SSE_EVENT_TOKEN,
)
from api.dependencies import get_reranker
from api.generate import stream_answer
from api.guard_input import GuardResult, guard_input
from api.guard_output import guard_output
from api.merge import Merged, merge_context
from api.rag_leg import RagLegResult, run_rag_leg
from api.rewrite import RoutedResult, fallback_route, rewrite_query
from api.sql_leg import SqlLegResult, run_sql_leg

logger = logging.getLogger("api.workflow")

STEP_TIMEOUTS = {
    "guard": 1.0,
    "rewrite": 4.0,
    "rag": 6.0,
    "sql": 2.0,
    "sql_nl2sql": 8.0,
    "rerank": 3.0,
    "output_guard": 2.0,
}

# Event callback: accepts async or sync callables (workflow awaits coroutines).
EventCallback = Callable[[str, dict], Awaitable[None] | None]


class QueryRejected(Exception):
    """L1 rejection — main maps this to HTTP 400 + audit."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"rejected: {reason}")


def parse_as_of(value: str | None) -> date | None:
    """Parse 'YYYY-MM-DD' to a date; None/invalid -> None (means today)."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except (ValueError, TypeError):
        logger.warning("as_of invalid (%r) — defaulting to today", value)
        return None


@dataclass
class PipelineTrace:
    steps: list[dict] = field(default_factory=list)

    def add(self, step: str, *, ok: bool, ms: int, detail: str = "") -> None:
        self.steps.append({"step": step, "ok": ok, "ms": ms, "detail": detail})


class RagQueryPipeline:
    """Runs the 8-step pipeline; returns the full answer payload plus internal trace."""

    def __init__(self, on_event: EventCallback | None = None):
        self.on_event: EventCallback = on_event or (lambda event, data: None)
        self.trace = PipelineTrace()

    async def _emit(self, event: str, data: dict) -> None:
        res = self.on_event(event, data)
        if inspect.isawaitable(res):
            await res

    async def run(
        self,
        query: str,
        session_id: str | None = None,
        as_of: str | None = None,
        history: list[dict] | None = None,
        on_event: EventCallback | None = None,
    ) -> dict:
        """Run the pipeline; raises QueryRejected on L1 rejection."""
        if on_event is not None:
            self.on_event = on_event
        self.trace = PipelineTrace()
        t0 = time.perf_counter()
        trace_id = "t-" + uuid.uuid4().hex[:10]
        as_of_date = parse_as_of(as_of)
        degraded: list[str] = []
        audit: dict[str, Any] = {
            "trace_id": trace_id,
            "session_id": session_id,
            "query": query,
            "latency_ms": None,
        }
        try:
            # 1. L1 input guard — hard reject on exfiltration/overlong input.
            guard: GuardResult
            try:
                guard = await asyncio.wait_for(guard_input(query), timeout=STEP_TIMEOUTS["guard"])
            except asyncio.TimeoutError:
                guard = GuardResult(clean=query, degraded=True)
                degraded.append("guard_timeout")
            self.trace.add("guard", ok=not guard.rejected, ms=_ms(t0))
            if guard.rejected:
                audit["guard_verdicts"] = {"L1": "reject", "reason": guard.reason}
                raise QueryRejected(guard.reason or "L1 rejected")
            if guard.degraded:
                degraded.append("guard_rule_only")

            # 2. Rewrite + route + SQL spec (one LLM JSON call).
            routed: RoutedResult
            try:
                routed = await asyncio.wait_for(
                    rewrite_query(guard.clean, history, as_of_date.isoformat() if as_of_date else None),
                    timeout=STEP_TIMEOUTS["rewrite"],
                )
            except asyncio.TimeoutError:
                routed = fallback_route(guard.clean, as_of_date.isoformat() if as_of_date else None, "rewrite_timeout")
                degraded.append("rewrite_timeout")
            except Exception as exc:  # noqa: BLE001
                routed = fallback_route(guard.clean, as_of_date.isoformat() if as_of_date else None, f"rewrite_error:{exc}")
                degraded.append("rewrite_error")
            degraded = _merge_flags(degraded, routed.degraded)
            self.trace.add("rewrite", ok=not routed.degraded, ms=_ms(t0), detail=routed.routing.get("structured_path", ""))

            audit.update(
                rewritten_query=routed.rewritten,
                routing=routed.routing,
                structured_path=routed.routing.get("structured_path"),
                sql_spec=routed.sql_spec or None,
            )

            # 3. RAG and SQL legs run in parallel (asyncio.gather fallback).
            needs_rag = bool(routed.routing.get("needs_rag", True))
            needs_sql = bool(routed.routing.get("needs_sql", False))
            path = routed.routing.get("structured_path", "none")

            spec_for_leg = routed.sql_spec or {}
            if path == "nl2sql":
                spec_for_leg = dict(spec_for_leg)
                spec_for_leg["structured_path"] = "nl2sql"

            rag_result = RagLegResult([], degraded=True, error="not_run")
            sql_result = SqlLegResult([], {"mode": "none", "error": "not_run"}, degraded=False)

            async def _rag_wrap() -> RagLegResult:
                return await run_rag_leg(routed.rewritten, routed.hl_keywords, routed.ll_keywords, as_of_date)

            async def _sql_wrap() -> SqlLegResult:
                return await run_sql_leg(spec_for_leg, as_of_date, guard.clean)

            tasks: list[tuple[str, asyncio.Task]] = []
            if needs_rag:
                tasks.append(("rag", asyncio.create_task(asyncio.wait_for(_rag_wrap(), STEP_TIMEOUTS["rag"]))))
            if needs_sql:
                sql_timeout = STEP_TIMEOUTS["sql_nl2sql"] if path == "nl2sql" else STEP_TIMEOUTS["sql"]
                tasks.append(("sql", asyncio.create_task(asyncio.wait_for(_sql_wrap(), sql_timeout))))

            if tasks:
                await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)

            for name, task in tasks:
                try:
                    result = task.result()
                except (asyncio.TimeoutError, TimeoutError):
                    degraded.append(f"{name}_timeout")
                    continue
                except Exception as exc:  # noqa: BLE001
                    logger.warning("leg %s crashed: %s", name, exc)
                    degraded.append(f"{name}_error")
                    continue
                if name == "rag":
                    rag_result = result
                    if rag_result.degraded:
                        degraded.append(f"rag_degraded:{rag_result.error or ''}")
                else:
                    sql_result = result
                    if sql_result.degraded:
                        degraded.append(f"sql_degraded:{sql_result.meta.get('error') or ''}")

            self.trace.add("legs", ok=True, ms=_ms(t0), detail=f"rag_chunks={len(rag_result.chunks)} sql_rows={len(sql_result.rows)}")
            audit["sql_query"] = sql_result.meta.get("sql_query")  # redacted in audit
            audit["fact_ids"] = [e.get("fact_id") for e in sql_result.rows if e.get("fact_id")]
            audit["chunk_ids"] = [c.get("id") for c in rag_result.chunks if c.get("id")]

            # 4. Rerank (RAG-only) then merge both legs into context blocks.
            chunks = rag_result.chunks
            try:
                chunks = await asyncio.wait_for(
                    get_reranker().rerank(routed.rewritten, chunks), timeout=STEP_TIMEOUTS["rerank"]
                )
            except asyncio.TimeoutError:
                degraded.append("rerank_timeout")
            except Exception as exc:  # noqa: BLE001
                degraded.append(f"rerank_error:{exc}")
            if any(c.get("_rerank_degraded") or c.get("_rerank_off") for c in chunks):
                degraded.append("rerank_degraded")
            audit["rerank_scores"] = [c.get("score") for c in chunks]

            merged: Merged = await merge_context(guard.clean, chunks, sql_result.rows, as_of_date)
            merged.meta.update(
                query=guard.clean,
                rewritten=routed.rewritten,
                as_of=as_of_date.isoformat() if as_of_date else None,
                degraded=degraded,
                sql_row_count=len(sql_result.rows),
                has_approx=any(e.get("quality") in ("range", "approx") for e in sql_result.rows),
            )

            # SSE: sources before facts (event order in the SS contract).
            await self._emit(SSE_EVENT_SOURCES, {"sources": merged.sources})
            await self._emit(SSE_EVENT_FACTS, {"facts": merged.facts})
            self.trace.add("merge", ok=True, ms=_ms(t0), detail=f"sources={len(merged.sources)}")

            # 5. Generate answer (streamed tokens).
            answer_parts: list[str] = []
            async for token in stream_answer(merged, history, routed.high_stakes):
                answer_parts.append(token)
                await self._emit(SSE_EVENT_TOKEN, {"text": token})
            answer = "".join(answer_parts)
            audit.update(
                model=merged.meta.get("model"),
                prompt_hash=merged.meta.get("prompt_hash"),
                answer_hash=sha256_hex(answer),
            )
            self.trace.add("generate", ok=bool(answer), ms=_ms(t0))

            # 6. L4 output guard — confidence + requires_review.
            strong_chunks = sum(1 for c in chunks if float(c.get("score", 0.0)) >= 0.8)
            merged.meta["strong_chunks"] = strong_chunks
            try:
                guard_res = await asyncio.wait_for(
                    guard_output(answer, merged.facts, merged.sources, routed.routing, meta=merged.meta),
                    timeout=STEP_TIMEOUTS["output_guard"],
                )
            except asyncio.TimeoutError:
                from api.guard_output import GuardResult

                guard_res = GuardResult(confidence="MEDIUM", requires_review=False, verdicts={"timeout": True})
                degraded.append("output_guard_timeout")
            self.trace.add("output_guard", ok=guard_res.confidence != "LOW", ms=_ms(t0), detail=guard_res.confidence)
            audit.update(confidence=guard_res.confidence, guard_verdicts=guard_res.verdicts)

            # Finalize payload for JSON mode / audit.
            latency_ms = int((time.perf_counter() - t0) * 1000)
            audit.update(latency_ms=latency_ms, degraded=degraded)
            payload = {
                "answer": answer,
                "sources": merged.sources,
                "facts": merged.facts,
                "confidence": guard_res.confidence,
                "requires_review": guard_res.requires_review,
                "routing": routed.routing,
                "trace_id": trace_id,
                "latency_ms": latency_ms,
            }
            return payload

        except QueryRejected:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            audit["latency_ms"] = latency_ms
            audit["degraded"] = degraded
            raise
        except Exception as exc:  # noqa: BLE001 — never crash the pipeline
            logger.exception("pipeline internal error")
            degraded.append(f"pipeline_error:{exc}")
            latency_ms = int((time.perf_counter() - t0) * 1000)
            audit.update(
                confidence="LOW",
                guard_verdicts={"pipeline": "error"},
                degraded=degraded,
                latency_ms=latency_ms,
            )
            return {
                "answer": "Xin lỗi, hệ thống xử lý câu hỏi gặp lỗi tạm thời. Vui lòng thử lại sau.",
                "sources": [],
                "facts": [],
                "confidence": "LOW",
                "requires_review": True,
                "routing": {"needs_rag": True, "needs_sql": False, "structured_path": "none"},
                "trace_id": trace_id,
                "latency_ms": latency_ms,
            }
        finally:
            # 7. Audit (append-only, never fails the pipeline).
            try:
                await write_audit(audit)
            except Exception:  # noqa: BLE001
                logger.exception("audit write in finally failed (ignored)")


def _merge_flags(base: list[str], more: list[str]) -> list[str]:
    """Union of two degradation-flag lists, preserving order and dedup."""
    out = list(base)
    for f in more or []:
        if f and f not in out:
            out.append(f)
    return out


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)
