"""Dependency factories — cached singletons behind lazy proxies.

Factories read Settings on first use so the api package imports cleanly before
configuration is ready (parallel scaffolding / smoke imports). Call sites should
prefer get_llm() / get_reranker() from here over direct adapter construction.
"""

from __future__ import annotations

from typing import Any

from api.adapters.google_places import GooglePlaces
from api.adapters.http_rerank import HttpRerank
from api.adapters.lightrag import LightRag
from api.adapters.noop import NoopRerank
from api.adapters.openai_compatible_llm import OpenAICompatibleLLM
from api.adapters.postgres_sql import PostgresSql
from api.adapters.static_places import StaticPlaces
from api.config import get_settings
from api.constants import (
    DEFAULT_MODEL_ANSWER,
    DEFAULT_RERANK_MODEL,
    MODEL_ROLE_FIELD,
    RERANK_BINDINGS,
)
from api.ports.geo import GeoPort
from api.ports.llm import LLMChatPort
from api.ports.rag import RagPort
from api.ports.rerank import RerankPort
from api.ports.sql import SqlPort

_llm: OpenAICompatibleLLM | None = None
_reranker: RerankPort | None = None
_geo: GeoPort | None = None
_rag: RagPort | None = None
_sql: SqlPort | None = None


def get_llm() -> LLMChatPort:
    """Build (once) the chat adapter from Settings; raises LLMConfigError if unconfigured."""
    global _llm
    if _llm is None:
        s = get_settings()
        # Auto-switch to Jina fallback credentials when LLM binding targets jina
        _is_jina = "jina" in (s.llm_base_url or "").lower()
        _llm_api_key = s.llm_api_key or (s.jina_llm_api_key if _is_jina else "")
        _llm_base = s.llm_base_url_v1 or s.jina_llm_base_url
        _llm = OpenAICompatibleLLM(
            api_key=_llm_api_key,
            base_url=_llm_base,
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
            # Auto-switch to Jina fallback credentials when binding is jina
            _rk = s.rerank_api_key or (s.jina_rerank_api_key if binding == "jina" else "")
            _rb = s.rerank_base_url or (s.jina_rerank_base_url if binding == "jina" else "")
            _reranker = HttpRerank(
                api_key=_rk,
                base_url=_rb,
                binding=binding,
                model=s.rerank_model or DEFAULT_RERANK_MODEL,
            )
    return _reranker


def model_for_role(role: str) -> str:
    """Default model for a role (e.g. 'rewrite' -> LLM_MODEL_REWRITE)."""
    s = get_settings()
    field = MODEL_ROLE_FIELD.get(role, "llm_model_answer")
    return getattr(s, field, None) or s.llm_model_answer or DEFAULT_MODEL_ANSWER


def get_geo() -> GeoPort:
    """Build (once) the geo adapter — GooglePlaces when configured, else StaticPlaces."""
    global _geo
    if _geo is None:
        s = get_settings()
        binding = (s.geo_binding or "").strip().lower()
        if binding == "google" and s.geo_api_key:
            _geo = GooglePlaces(
                api_key=s.geo_api_key,
                base_url=s.geo_base_url,
                radius_m=s.geo_radius_m,
            )
        else:
            _geo = StaticPlaces(path=s.geo_static_path, radius_m=s.geo_radius_m)
    return _geo


def get_rag() -> RagPort:
    """Build (once) the RAG adapter — lazy LightRAG singleton behind the port."""
    global _rag
    if _rag is None:
        _rag = LightRag()
    return _rag


def get_sql() -> SqlPort:
    """Build (once) the read-only SQL adapter (R1 spec + R2 NL2SQL)."""
    global _sql
    if _sql is None:
        _sql = PostgresSql()
    return _sql


class LazyLLMProxy:
    """Forwards attribute access to the real adapter, built on first use.

    Lets `from api.dependencies import llm` stay import-safe pre-config.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(get_llm(), name)


llm: LLMChatPort = LazyLLMProxy()  # type: ignore[assignment]
