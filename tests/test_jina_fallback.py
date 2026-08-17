"""Tests for Jina AI fallback provider integration."""

from __future__ import annotations

import pytest

from api import constants
from api.adapters.http_rerank import HttpRerank



def test_rerank_bindings_includes_jina():
    assert "jina" in constants.RERANK_BINDINGS
    assert constants.RERANK_BINDINGS == ("dashscope", "aibox", "jina")


def test_rerank_endpoint_jina_exists():
    assert hasattr(constants, "RERANK_ENDPOINT_JINA")
    assert constants.RERANK_ENDPOINT_JINA == "/v1/rerank"

@pytest.mark.asyncio
async def test_http_rerank_jina_routing_uses_jina_endpoint(monkeypatch):
    calls: list[dict] = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"results": [
                {"index": 0, "relevance_score": 0.9},
                {"index": 1, "relevance_score": 0.3}
            ]}
        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, *, json=None, headers=None):
            calls.append({"url": url, "json": json, "headers": headers})
            return FakeResp()

    monkeypatch.setattr("api.adapters.http_rerank.httpx.AsyncClient", FakeClient)

    reranker = HttpRerank(
        api_key="fake-jina-key",
        base_url="https://api.jina.ai",
        binding="jina",
        model="jina-reranker-v3.5",
    )
    chunks = [{"content": "doc A"}, {"content": "doc B"}]
    result = await reranker.rerank("test query", chunks)

    assert len(calls) == 1
    assert "/v1/rerank" in calls[0]["url"]
    assert "Bearer fake-jina-key" in calls[0]["headers"]["Authorization"]
    assert calls[0]["json"]["model"] == "jina-reranker-v3.5"
    assert result[0]["score"] == 0.9
    assert result[1]["score"] == 0.3


@pytest.mark.asyncio
async def test_http_rerank_dashscope_routing(monkeypatch):
    calls: list[dict] = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"results": []}
        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, *, json=None, headers=None):
            calls.append({"url": url})
            return FakeResp()

    monkeypatch.setattr("api.adapters.http_rerank.httpx.AsyncClient", FakeClient)

    reranker = HttpRerank(
        api_key="fake",
        base_url="https://dashscope.aliyuncs.com/compatible-mode",
        binding="dashscope",
    )
    await reranker.rerank("q", [{"content": "x"}])
    urls = [c["url"] for c in calls]
    assert any("/v1/reranks" in u for u in urls)


@pytest.mark.asyncio
async def test_http_rerank_aibox_routing(monkeypatch):
    calls: list[dict] = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"results": []}
        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, *, json=None, headers=None):
            calls.append({"url": url})
            return FakeResp()

    monkeypatch.setattr("api.adapters.http_rerank.httpx.AsyncClient", FakeClient)

    reranker = HttpRerank(
        api_key="fake",
        base_url="https://api.ai-box.vn",
        binding="aibox",
    )
    await reranker.rerank("q", [{"content": "x"}])
    urls = [c["url"] for c in calls]
    assert any("/v1/rerank" in u and "/v1/reranks" not in u for u in urls)

def test_config_jina_defaults():
    """Jina Settings fields exist with sensible defaults — verified via model_fields."""
    from api.config import Settings
    fields = Settings.model_fields
    assert "jina_embedding_api_key" in fields
    assert "jina_embedding_base_url" in fields
    assert "jina_embedding_model" in fields
    assert "jina_embedding_dim" in fields
    assert "jina_rerank_api_key" in fields
    assert "jina_rerank_base_url" in fields
    assert "jina_rerank_model" in fields
    assert "jina_llm_api_key" in fields
    assert "jina_llm_base_url" in fields
    assert "jina_llm_model_answer" in fields

    s = Settings()
    # Defaults should be the hardcoded values (not overridden by .env except for keys)
    assert s.jina_embedding_base_url == "https://api.jina.ai/v1"
    assert s.jina_embedding_model == "jina-embeddings-v3"
    assert s.jina_embedding_dim == 1024
    assert s.jina_rerank_base_url == "https://api.jina.ai"
    assert s.jina_rerank_model == "jina-reranker-v3.5"


def test_config_jina_fields_are_overridable():
    from api.config import Settings
    s = Settings(
        jina_embedding_api_key="test-key",
        jina_llm_model_answer="custom-model",
    )
    assert s.jina_embedding_api_key == "test-key"
    assert s.jina_llm_model_answer == "custom-model"


def test_llm_base_url_v1_normalises_bare_host():
    from api.config import Settings
    s = Settings(llm_base_url="https://api.example.com")
    assert s.llm_base_url_v1 == "https://api.example.com/v1"
    s2 = Settings(llm_base_url="https://api.example.com/v1")
    assert s2.llm_base_url_v1 == "https://api.example.com/v1"


def test_lightrag_accepts_jina_binding():
    """lightrag_init.py must include 'jina' in the accepted embedding bindings."""
    import ingest.lightrag_init as li
    source = open(li.__file__, encoding="utf-8").read()
    assert "jina" in source
    assert "embedding_binding in" in source


def test_dependencies_use_jina_creds():
    """dependencies.py must reference jina_* fields for fallback."""
    import api.dependencies as deps
    source = open(deps.__file__, encoding="utf-8").read()
    assert "jina_llm_api_key" in source
    assert "jina_rerank_api_key" in source
    assert "jina_rerank_base_url" in source
