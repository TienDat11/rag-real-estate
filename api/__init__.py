"""api package — 8-step query pipeline (guard, rewrite, legs, merge, generate, output guard).

Modules are plain functions / testable classes; `workflow.py` orchestrates them.

This is the public API surface. Internal structure follows DDD:
- domain/ — pure business logic (entities, value objects, domain services)
- application/ — use cases and orchestration (services, pipelines)
- infrastructure/ — external adapters (config, database, ports & adapters)
- interfaces/ — API entry points (FastAPI)

Backward-compat exports for tests and external consumers.
"""

# Domain exports
from .domain.entities.price_calc import (
    parse_vn_number,
    extract_budget,
    extract_price_intent,
    floor_price_vnd,
    Offer,
    resolve_unit_type_key,
    cash_match,
    loan_match,
    affordability_rows,
    affordability_summary,
    analyze_affordability,
    offer_from_row,
    pricing_rows,
    pricing_summary,
    price_tiers_from_attrs,
    per_m2_range,
    resolve_unit_type_for_code,
    HIGHEST_SALE_INDEX,
    DEFAULT_TIER_BANDS,
    FLOOR_NORM,
)
from .domain.value_objects.constants import (
    DEFAULT_LLM_TIMEOUT_S,
    DEFAULT_RERANK_TIMEOUT_S,
    LLM_CALL_TIMEOUT_S,
    MAX_QUERY_LENGTH,
    MAX_INPUT_CHARS,
    SSE_EVENT_PLACES,
    SSE_EVENT_SOURCES,
    SSE_EVENT_FACTS,
    SSE_EVENT_TOKEN,
    SSE_EVENT_PROGRESS,
    SSE_EVENT_DONE,
    SSE_EVENT_ERROR,
    DEFAULT_MODEL_ANSWER,
    DEFAULT_MODEL_ANSWER_PRO,
    DEFAULT_MODEL_EXTRACT,
    DEFAULT_MODEL_GUARD,
    DEFAULT_MODEL_NL2SQL,
    DEFAULT_MODEL_REWRITE,
    MODEL_ROLE_FIELD,
    SUPPORTED_ROLES,
    RERANK_BINDINGS,
    DEFAULT_RERANK_MODEL,
    RERANK_ENDPOINT_DASHSCOPE,
    RERANK_ENDPOINT_AIBOX,
    RERANK_ENDPOINT_JINA,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_MAX_ENTITY_TOKENS,
    DEFAULT_MAX_RELATION_TOKENS,
    DEFAULT_MAX_TOTAL_TOKENS,
)
from .domain.services.route_intent import Intent, ClassifyResult, classify_intent
from .domain.services.rewrite import (
    RoutedResult,
    fallback_route,
    rewrite_query,
    detect_aggregate_intent,
    detect_pricing_intent,
    HIGH_STAKES_KEYWORDS,
    AGGREGATE_KEYWORDS,
    GEO_INTENT_KEYWORDS,
    _normalize_routed,
)
from .domain.services.guard_input import GuardResult as InputGuardResult, guard_input, rule_screen
from .domain.services.guard_output import GuardResult as OutputGuardResult, guard_output
from .domain.services.rerank import rerank
from .domain.services.llm import (
    LLMClient,
    LLMConfigError,
    LLMError,
    LLMTimeoutError,
    LazyLLMProxy,
    MODEL_ROLE_FIELD,
    OpenAICompatibleLLM,
    get_llm,
    llm,
    model_for_role,
)
from .domain.services.nl2sql_guard import (
    Sqlnl2sqlError,
    validate_sql,
    extract_sql,
    run_nl2sql,
    close_nl2sql_pool,
)
from .domain.services.utils import (
    sha256_hex,
    utc_now_iso,
    safe_float,
    truncate_str,
    slugify,
)

# Application exports
from .application.services.sql_leg import (
    SqlLegResult,
    SpecError,
    SqlLegError,
    build_dsn,
    get_ro_pool,
    close_ro_pool,
    run_sql_leg,
    ALLOWED_SOURCES,
    ALLOWED_FIELDS,
    ALLOWED_OPS,
    OFFER_COLUMNS,
)
from .application.services.rag_leg import (
    RagLegResult,
    run_rag_leg,
    get_lightrag,
    LIGHTRAG_READY,
)
from .application.services.merge import (
    Merged,
    merge_context,
    build_rag_context,
    build_evidence_context,
    build_sources,
    build_facts,
    hydrate_chunks,
)
from .application.services.generate import (
    stream_answer,
    build_messages,
)
from .application.services.audit import (
    write_audit,
    close_audit_pool,
    redact_sql_spec,
    redact_sql_query,
)
from .application.pipelines.workflow import (
    RagQueryWorkflow,
    QueryRejected,
    STEP_TIMEOUTS,
    GuardedEv,
    RagRequestEv,
    SqlRequestEv,
    GeoRequestEv,
    RagDoneEv,
    SqlDoneEv,
    GeoDoneEv,
    MergedEv,
    GeneratedEv,
    parse_as_of,
)

# Infrastructure exports
from .infrastructure.config.config import (
    Settings,
    get_settings,
    export_runtime_env,
)
from .infrastructure.dependencies import (
    get_llm,
    get_reranker,
    get_geo,
    get_rag,
    get_sql,
    model_for_role,
)
from .infrastructure.ports import (
    GeoPlace,
    GeoPort,
    GeoResult,
    LLMChatPort,
    RagChunk,
    RagPort,
    RagResult,
    RerankPort,
    SqlPort,
    SqlResult,
)
from .infrastructure.adapters import (
    GooglePlaces,
    HttpRerank,
    LightRag,
    NoopRerank,
    LLMConfigError,
    LLMError,
    LLMTimeoutError,
    OpenAICompatibleLLM,
    PostgresSql,
    StaticPlaces,
)

# Interface exports
from .interfaces.api.main import create_app, app

# Backward-compat submodule aliases
import sys

# Directly expose the actual submodules by their canonical paths
_api_pkg = sys.modules[__name__]

# api.config
sys.modules[__name__ + ".config"] = sys.modules[__name__ + ".infrastructure.config.config"]

# api.adapters  
_infra_adapters = sys.modules[__name__ + ".infrastructure.adapters"]
sys.modules[__name__ + ".adapters"] = _infra_adapters
_api_pkg.adapters = _infra_adapters

# api.adapters submodules
for _name in ["google_places", "http_rerank", "lightrag", "noop", "openai_compatible_llm", "postgres_sql", "static_places"]:
    try:
        _mod = __import__(f"{__name__}.infrastructure.adapters.{_name}", fromlist=["*"])
        sys.modules[__name__ + ".adapters." + _name] = _mod
        setattr(_infra_adapters, _name, _mod)
    except ImportError:
        pass

# api.ports
_infra_ports = sys.modules[__name__ + ".infrastructure.ports"]
sys.modules[__name__ + ".ports"] = _infra_ports
_api_pkg.ports = _infra_ports

# api.ports submodules
for _name in ["geo", "llm", "rag", "rerank", "sql"]:
    try:
        _mod = __import__(f"{__name__}.infrastructure.ports.{_name}", fromlist=["*"])
        sys.modules[__name__ + ".ports." + _name] = _mod
        setattr(_infra_ports, _name, _mod)
    except ImportError:
        pass

# api.rewrite - expose the actual module
_rewrite_mod = __import__(f"{__name__}.domain.services.rewrite", fromlist=["*"])
sys.modules[__name__ + ".rewrite"] = _rewrite_mod
_rewrite_mod.llm = _infra_adapters  # monkeypatch target
_rewrite_mod.model_for_role = model_for_role

# api.route_intent
_route_intent_mod = __import__(f"{__name__}.domain.services.route_intent", fromlist=["*"])
sys.modules[__name__ + ".route_intent"] = _route_intent_mod

# api.guard_input
_guard_input_mod = __import__(f"{__name__}.domain.services.guard_input", fromlist=["*"])
sys.modules[__name__ + ".guard_input"] = _guard_input_mod

# api.price_calc
_price_calc_mod = __import__(f"{__name__}.domain.entities.price_calc", fromlist=["*"])
sys.modules[__name__ + ".price_calc"] = _price_calc_mod

# api.utils
_utils_mod = __import__(f"{__name__}.domain.services.utils", fromlist=["*"])
sys.modules[__name__ + ".utils"] = _utils_mod

# api.constants
_constants_mod = __import__(f"{__name__}.domain.value_objects.constants", fromlist=["*"])
sys.modules[__name__ + ".constants"] = _constants_mod

# api.llm
_llm_mod = __import__(f"{__name__}.domain.services.llm", fromlist=["*"])
sys.modules[__name__ + ".llm"] = _llm_mod

# api.sql_leg
_sql_leg_mod = __import__(f"{__name__}.application.services.sql_leg", fromlist=["*"])
sys.modules[__name__ + ".sql_leg"] = _sql_leg_mod

# api.workflow
_workflow_mod = __import__(f"{__name__}.application.pipelines.workflow", fromlist=["*"])
sys.modules[__name__ + ".workflow"] = _workflow_mod

# api.nl2sql_guard
_nl2sql_guard_mod = __import__(f"{__name__}.domain.services.nl2sql_guard", fromlist=["*"])
sys.modules[__name__ + ".nl2sql_guard"] = _nl2sql_guard_mod
_api_pkg.nl2sql_guard = _nl2sql_guard_mod

# api.dependencies
_deps_mod = __import__(f"{__name__}.infrastructure.dependencies", fromlist=["*"])
sys.modules[__name__ + ".dependencies"] = _deps_mod

__all__ = [
    # Domain
    "parse_vn_number",
    "extract_budget",
    "extract_price_intent",
    "floor_price_vnd",
    "Offer",
    "resolve_unit_type_key",
    "cash_match",
    "loan_match",
    "affordability_rows",
    "affordability_summary",
    "analyze_affordability",
    "offer_from_row",
    "per_m2_range",
    "pricing_rows",
    "pricing_summary",
    "price_tiers_from_attrs",
    "resolve_unit_type_for_code",
    "HIGHEST_SALE_INDEX",
    "DEFAULT_TIER_BANDS",
    "FLOOR_NORM",
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
    "_normalize_routed",
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
    # Application
    "SqlLegResult",
    "SpecError",
    "SqlLegError",
    "build_dsn",
    "get_ro_pool",
    "close_ro_pool",
    "run_sql_leg",
    "ALLOWED_SOURCES",
    "ALLOWED_FIELDS",
    "ALLOWED_OPS",
    "OFFER_COLUMNS",
    "RagLegResult",
    "run_rag_leg",
    "get_lightrag",
    "LIGHTRAG_READY",
    "Merged",
    "merge_context",
    "build_rag_context",
    "build_evidence_context",
    "build_sources",
    "build_facts",
    "hydrate_chunks",
    "stream_answer",
    "build_messages",
    "write_audit",
    "close_audit_pool",
    "redact_sql_spec",
    "redact_sql_query",
    "RagQueryWorkflow",
    "QueryRejected",
    "STEP_TIMEOUTS",
    "GuardedEv",
    "RagRequestEv",
    "SqlRequestEv",
    "GeoRequestEv",
    "RagDoneEv",
    "SqlDoneEv",
    "GeoDoneEv",
    "MergedEv",
    "GeneratedEv",
    "parse_as_of",
    # Infrastructure
    "Settings",
    "get_settings",
    "export_runtime_env",
    "get_llm",
    "get_reranker",
    "get_geo",
    "get_rag",
    "get_sql",
    "model_for_role",
    "GeoPlace",
    "GeoPort",
    "GeoResult",
    "LLMChatPort",
    "RagChunk",
    "RagPort",
    "RagResult",
    "RerankPort",
    "SqlPort",
    "SqlResult",
    "GooglePlaces",
    "HttpRerank",
    "LightRag",
    "NoopRerank",
    "LLMConfigError",
    "LLMError",
    "LLMTimeoutError",
    "OpenAICompatibleLLM",
    "PostgresSql",
    "StaticPlaces",
    # Interface
    "create_app",
    "app",
]
