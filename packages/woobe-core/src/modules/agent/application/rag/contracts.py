"""RAG application contracts.

The canonical port surface lives under ``application.interfaces`` so infrastructure
can depend on it without crossing the Agent module architecture boundary. This
module remains as the application-facing import path used by strategies and tests.
"""

from modules.agent.application.interfaces.rag import (
    RAGCapabilities,
    RAGEmbeddingCapability,
    RAGRequest,
    RAGResult,
    RAGStrategy,
    RAGStrategyResolver,
    RAGVectorSearchCapability,
)

__all__ = [
    "RAGCapabilities",
    "RAGEmbeddingCapability",
    "RAGRequest",
    "RAGResult",
    "RAGStrategy",
    "RAGStrategyResolver",
    "RAGVectorSearchCapability",
]
