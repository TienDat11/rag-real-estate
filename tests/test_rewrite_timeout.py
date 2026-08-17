"""Regression tests for rewrite-router timeout handling (BE perf fix).

A TIMEOUT from the LLM must NOT burn the JSON-correction retry (worst case
2 x LLM_CALL_TIMEOUT_S = 40s before the rag-only fallback). The correction
prompt only helps when the LLM actually answered with malformed JSON; when
the call timed out we fall back immediately after a single LLM call.
"""

import asyncio
import json

from api import rewrite
from api.llm import LLMTimeoutError


class _FakeLLM:
    """Minimal stand-in for api.dependencies.llm with canned results."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def complete(self, msgs, json_mode=False, model=None, timeout=None):
        self.calls += 1
        out = self._results.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def _routed_json(rewritten="Căn CH-10 nhìn ra biển", **routing):
    return {
        "rewritten_query": rewritten,
        "routing": {
            "needs_rag": True,
            "needs_sql": False,
            "structured_path": "none",
            "high_stakes": False,
            "needs_geo": False,
            **routing,
        },
        "hl_keywords": [],
        "ll_keywords": [],
        "high_stakes": False,
    }


def test_rewrite_timeout_does_not_retry(monkeypatch):
    """A 20s LLM timeout falls back after ONE attempt (not two)."""
    fake = _FakeLLM(
        [LLMTimeoutError("LLM complete timeout (20.0s) model=deepseek-v4-flash")]
    )
    monkeypatch.setattr(rewrite, "llm", fake)

    async def go():
        return await rewrite.rewrite_query(
            "Căn CH-10 có nhìn ra biển được không?", None, None
        )

    res = asyncio.run(go())

    assert fake.calls == 1  # timeout must not trigger the JSON-correction retry
    assert res.routing["needs_rag"] is True
    assert res.routing["needs_sql"] is False
    assert res.routing["structured_path"] == "none"
    assert res.degraded and "timeout" in res.degraded[0]


def test_rewrite_malformed_json_retries_once(monkeypatch):
    """Malformed JSON (the LLM DID answer) still retries once, then normalizes."""
    fake = _FakeLLM(["not valid json at all", json.dumps(_routed_json())])
    monkeypatch.setattr(rewrite, "llm", fake)

    async def go():
        return await rewrite.rewrite_query("q", None, None)

    res = asyncio.run(go())

    assert fake.calls == 2  # JSON-correction retry is preserved
    assert res.routing["needs_rag"] is True
    assert res.routing["structured_path"] == "none"
    assert res.routing["needs_sql"] is False
