"""Dependency factories — cached singletons behind lazy proxies.

Factories read Settings on first use so the api package imports cleanly before
configuration is ready (parallel scaffolding / smoke imports). Call sites should
prefer get_llm() / get_reranker() from here over direct adapter construction.
"""

from __future__ import annotations

from typing import Any

from api.adapters.http_rerank import HttpRerank
from api.adapters.noop import NoopRerank
from api.adapters.openai_compatible_llm import OpenAICompatibleLLM
from api.config import get_settings
from api.constants import (
    DEFAULT_MODEL_ANSWER,
    DEFAULT_RERANK_MODEL,
    MODEL_ROLE_FIELD,
    RERANK_BINDINGS,
)
from api.ports.llm import LLMChatPort
from api.ports.rerank import RerankPort

_llm: OpenAICompatibleLLM | None = None
_reranker: RerankPort | None = None


def get_llm() -> LLMChatPort:
    """Build (once) the chat adapter from Settings; raises LLMConfigError if unconfigured."""
    global _llm
    if _llm is None:
        s = get_settings()
        _llm = OpenAICompatibleLLM(
            api_key=s.llm_api_key or "",
            base_url=s.llm_base_url or "",
            default_model=s.llm_model_answer or DEFAULT_MODEL_ANSWER,
        )
    return _llm


def get_reranker() -> RerankPort:
    """Build (once) the rerank adapter — NoopRerank when disabled by config."""
    global _reranker
    if _reranker is None:
        s = get_settings()
        binding = (s.rerank_binding or "").strip().lower()
        if not s.enable_rerank or binding not in RERANK_BINDINGS:
            _reranker = NoopRerank()
        else:
            _reranker = HttpRerank(
                api_key=s.rerank_api_key or "",
                base_url=s.rerank_base_url or "",
                binding=binding,
                model=s.rerank_model or DEFAULT_RERANK_MODEL,
            )
    return _reranker


def model_for_role(role: str) -> str:
    """Default model for a role (e.g. 'rewrite' -> LLM_MODEL_REWRITE)."""
    s = get_settings()
    field = MODEL_ROLE_FIELD.get(role, "llm_model_answer")
    return getattr(s, field, None) or s.llm_model_answer or DEFAULT_MODEL_ANSWER


class LazyLLMProxy:
    """Forwards attribute access to the real adapter, built on first use.

    Lets `from api.dependencies import llm` stay import-safe pre-config.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_llm(), name)


llm: LLMChatPort = LazyLLMProxy()  # type: ignore[assignment]
