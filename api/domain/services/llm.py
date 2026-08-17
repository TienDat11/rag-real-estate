"""Back-compat shim — factories/adapters now live in api.dependencies / api.adapters.

Kept so legacy `from api.llm import llm, model_for_role, LLMClient` imports work.
"""

from __future__ import annotations

import sys

from ..value_objects.constants import MODEL_ROLE_FIELD

# Lazy imports to avoid circular dependency - use module __getattr__ for true lazy loading
_lazy_modules = {}


def _get_llm_config_error():
    if "LLMConfigError" not in _lazy_modules:
        from ...infrastructure.adapters.openai_compatible_llm import LLMConfigError
        _lazy_modules["LLMConfigError"] = LLMConfigError
    return _lazy_modules["LLMConfigError"]


def _get_llm_error():
    if "LLMError" not in _lazy_modules:
        from ...infrastructure.adapters.openai_compatible_llm import LLMError
        _lazy_modules["LLMError"] = LLMError
    return _lazy_modules["LLMError"]


def _get_llm_timeout_error():
    if "LLMTimeoutError" not in _lazy_modules:
        from ...infrastructure.adapters.openai_compatible_llm import LLMTimeoutError
        _lazy_modules["LLMTimeoutError"] = LLMTimeoutError
    return _lazy_modules["LLMTimeoutError"]


def _get_openai_compatible_llm():
    if "OpenAICompatibleLLM" not in _lazy_modules:
        from ...infrastructure.adapters.openai_compatible_llm import OpenAICompatibleLLM
        _lazy_modules["OpenAICompatibleLLM"] = OpenAICompatibleLLM
    return _lazy_modules["OpenAICompatibleLLM"]


def _get_lazy_llm_proxy():
    if "LazyLLMProxy" not in _lazy_modules:
        from ...infrastructure.dependencies import LazyLLMProxy
        _lazy_modules["LazyLLMProxy"] = LazyLLMProxy
    return _lazy_modules["LazyLLMProxy"]


def _get_get_llm():
    if "get_llm" not in _lazy_modules:
        from ...infrastructure.dependencies import get_llm
        _lazy_modules["get_llm"] = get_llm
    return _lazy_modules["get_llm"]


def _get_model_for_role():
    if "model_for_role" not in _lazy_modules:
        from ...infrastructure.dependencies import model_for_role
        _lazy_modules["model_for_role"] = model_for_role
    return _lazy_modules["model_for_role"]


# Module-level __getattr__ for Python 3.7+ lazy loading
def __getattr__(name):
    if name == "LLMConfigError":
        return _get_llm_config_error()
    if name == "LLMError":
        return _get_llm_error()
    if name == "LLMTimeoutError":
        return _get_llm_timeout_error()
    if name == "OpenAICompatibleLLM":
        return _get_openai_compatible_llm()
    if name == "LazyLLMProxy":
        return _get_lazy_llm_proxy()
    if name == "MODEL_ROLE_FIELD":
        return MODEL_ROLE_FIELD
    if name == "get_llm":
        return _get_get_llm()
    if name == "model_for_role":
        return _get_model_for_role()
    if name == "LLMClient":
        return _get_openai_compatible_llm()
    if name == "llm":
        # Create a proxy that forwards to the real get_llm
        class _LLMProxy:
            def __getattr__(self, name):
                return getattr(_get_get_llm(), name)
        return _LLMProxy()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LLMClient",
    "LLMConfigError",
    "LLMError",
    "LLMTimeoutError",
    "LazyLLMProxy",
    "MODEL_ROLE_FIELD",
    "OpenAICompatibleLLM",
    "get_llm",
    "llm",
    "model_for_role",
]
