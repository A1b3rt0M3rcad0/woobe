from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import UUID

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.rag.capabilities.embedding import RAGEmbeddingCapability
from modules.agent.application.rag.capabilities.vector_search import RAGVectorSearchCapability


@dataclass(frozen=True, slots=True)
class RAGRequest:
    """Immutable input presented to one RAG strategy invocation."""

    query: str
    history: tuple[Any, ...]
    config: RAGRuntimeConfig
    vector_snapshot_id: UUID
    snapshot_documents: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class RAGResult:
    """Strategy output consumed by the runtime adapter and Context Manager."""

    context: str | None
    sources: tuple[SourceInfo, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RAGCapabilities:
    """Operations a strategy may compose without knowing their infrastructure."""

    embedding: RAGEmbeddingCapability
    vector_search: RAGVectorSearchCapability


@runtime_checkable
class RAGStrategy(Protocol):
    async def retrieve(
        self,
        request: RAGRequest,
        capabilities: RAGCapabilities,
    ) -> RAGResult: ...
