"""Domain services — pure business logic, testable without I/O."""

from .route_intent import Intent, ClassifyResult, classify_intent
from .rewrite import (
    RoutedResult,
    fallback_route,
    rewrite_query,
    detect_aggregate_intent,
    detect_pricing_intent,
    HIGH_STAKES_KEYWORDS,
    AGGREGATE_KEYWORDS,
    GEO_INTENT_KEYWORDS,
)
from .guard_input import GuardResult as InputGuardResult, guard_input, rule_screen
from .guard_output import GuardResult as OutputGuardResult, guard_output
from .rerank import rerank
from .nl2sql_guard import (
    Sqlnl2sqlError,
    validate_sql,
    extract_sql,
    run_nl2sql,
    close_nl2sql_pool,
)
from .utils import (
    sha256_hex,
    utc_now_iso,
    safe_float,
    truncate_str,
    slugify,
)

# Lazy re-exports from llm to avoid circular imports
class _LazyLLMExports:
    @property
    def LLMClient(self):
        from .llm import LLMClient
        return LLMClient
    
    @property
    def LLMConfigError(self):
        from .llm import LLMConfigError
        return LLMConfigError
    
    @property
    def LLMError(self):
        from .llm import LLMError
        return LLMError
    
    @property
    def LLMTimeoutError(self):
        from .llm import LLMTimeoutError
        return LLMTimeoutError
    
    @property
    def LazyLLMProxy(self):
        from .llm import LazyLLMProxy
        return LazyLLMProxy
    
    @property
    def MODEL_ROLE_FIELD(self):
        from .llm import MODEL_ROLE_FIELD
        return MODEL_ROLE_FIELD
    
    @property
    def OpenAICompatibleLLM(self):
        from .llm import OpenAICompatibleLLM
        return OpenAICompatibleLLM
    
    @property
    def get_llm(self):
        from .llm import get_llm
        return get_llm
    
    @property
    def llm(self):
        from .llm import llm
        return llm
    
    @property
    def model_for_role(self):
        from .llm import model_for_role
        return model_for_role

_lazy_llm = _LazyLLMExports()

LLMClient = _lazy_llm.LLMClient
LLMConfigError = _lazy_llm.LLMConfigError
LLMError = _lazy_llm.LLMError
LLMTimeoutError = _lazy_llm.LLMTimeoutError
LazyLLMProxy = _lazy_llm.LazyLLMProxy
MODEL_ROLE_FIELD = _lazy_llm.MODEL_ROLE_FIELD
OpenAICompatibleLLM = _lazy_llm.OpenAICompatibleLLM
get_llm = _lazy_llm.get_llm
llm = _lazy_llm.llm
model_for_role = _lazy_llm.model_for_role


__all__ = [
    "Intent",
    "ClassifyResult",
    "classify_intent",
    "RoutedResult",
    "fallback_route",
    "rewrite_query",
    "detect_aggregate_intent",
    "detect_pricing_intent",
    "HIGH_STAKES_KEYWORDS",
    "AGGREGATE_KEYWORDS",
    "GEO_INTENT_KEYWORDS",
    "InputGuardResult",
    "guard_input",
    "rule_screen",
    "OutputGuardResult",
    "guard_output",
    "rerank",
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
    "Sqlnl2sqlError",
    "validate_sql",
    "extract_sql",
    "run_nl2sql",
    "close_nl2sql_pool",
    "sha256_hex",
    "utc_now_iso",
    "safe_float",
    "truncate_str",
    "slugify",
]
