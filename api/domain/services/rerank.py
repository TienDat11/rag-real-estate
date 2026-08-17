"""Back-compat shim — rerank now resolves via api.dependencies.get_reranker().

Kept so legacy `from api.rerank import rerank` call sites keep working.
"""

from __future__ import annotations

import sys

# Lazy imports to avoid circular dependency - use module __getattr__ for true lazy loading
_lazy_modules = {}


def _get_http_rerank():
    if "HttpRerank" not in _lazy_modules:
        from ...infrastructure.adapters.http_rerank import HttpRerank
        _lazy_modules["HttpRerank"] = HttpRerank
    return _lazy_modules["HttpRerank"]


def _get_noop_rerank():
    if "NoopRerank" not in _lazy_modules:
        from ...infrastructure.adapters.noop import NoopRerank
        _lazy_modules["NoopRerank"] = NoopRerank
    return _lazy_modules["NoopRerank"]


def _get_get_reranker():
    if "get_reranker" not in _lazy_modules:
        from ...infrastructure.dependencies import get_reranker
        _lazy_modules["get_reranker"] = get_reranker
    return _lazy_modules["get_reranker"]


# Module-level __getattr__ for Python 3.7+ lazy loading
def __getattr__(name):
    if name == "HttpRerank":
        return _get_http_rerank()
    if name == "NoopRerank":
        return _get_noop_rerank()
    if name == "get_reranker":
        return _get_get_reranker()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def rerank(query: str, chunks: list[dict]) -> list[dict]:
    """Score chunks through the configured rerank adapter; never raises."""
    return await _get_get_reranker().rerank(query, chunks)


__all__ = ["HttpRerank", "NoopRerank", "get_reranker", "rerank"]
