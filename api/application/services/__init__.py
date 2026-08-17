"""Application services — SQL, RAG, merge, generate, audit."""

from .sql_leg import (
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
from .rag_leg import (
    RagLegResult,
    run_rag_leg,
    get_lightrag,
    LIGHTRAG_READY,
)
from .merge import (
    Merged,
    merge_context,
    build_rag_context,
    build_evidence_context,
    build_sources,
    build_facts,
    hydrate_chunks,
)
from .generate import (
    stream_answer,
    build_messages,
)
from .audit import (
    write_audit,
    close_audit_pool,
    redact_sql_spec,
    redact_sql_query,
)

__all__ = [
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
]