from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import UUID

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.dtos.runtime_dtos import SourceInfo


@runtime_checkable
class RAGEmbeddingCapability(Protocol):
    """Produce a query embedding without exposing provider/runtime details."""

    async def embed_query(self, text: str) -> list[float]: ...


@runtime_checkable
class RAGVectorSearchCapability(Protocol):
    """Search the accepted vector snapshot behind a persistence boundary."""

    async def search(
        self,
        *,
        vector_snapshot_id: UUID,
        embedding: list[float],
        limit: int,
        threshold: float,
    ) -> list[tuple[Any, float]]: ...


@dataclass(frozen=True, slots=True)
class RAGBinding:
    """Frozen Knowledge/RAG binding accepted for one Agent Run."""

    strategy: str
    config: RAGRuntimeConfig
    knowledge: Any
    snapshot: Any
    provider_model: Any
    credential: Any
    snapshot_documents: tuple[Any, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


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


@runtime_checkable
class RAGStrategyResolver(Protocol):
    """Resolve a configured RAG strategy without exposing registry implementation."""

    def resolve(self, name: str) -> RAGStrategy: ...
