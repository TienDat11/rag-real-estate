"""Domain ports for external services (Ports & Adapters).

The pipeline depends on these Protocols, never on concrete SDKs, so switching a
provider (aibox / DashScope / local) only adds a new adapter.
"""

from api.ports.llm import LLMChatPort
from api.ports.rerank import RerankPort

__all__ = ["LLMChatPort", "RerankPort"]
