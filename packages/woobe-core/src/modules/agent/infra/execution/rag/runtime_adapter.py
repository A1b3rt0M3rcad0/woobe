from __future__ import annotations

from typing import Any

from modules.agent.application.interfaces.embedding_errors import EmbeddingProviderError
from modules.agent.application.interfaces.embedding_factory import EmbeddingFactory
from modules.agent.application.interfaces.rag import (
    RAGBinding,
    RAGCapabilities,
    RAGRequest,
    RAGResult,
    RAGStrategyResolver,
    RAGVectorSearchCapability,
)
from modules.agent.infra.execution.rag.embedding_capability import (
    RuntimeEmbeddingCapability,
)
from shared.contracts.errors import ValidationError


class RAGRuntimeAdapter:
    """Execute one frozen RAG binding without reaching back into Agent/runtime state."""

    def __init__(
        self,
        *,
        registry: RAGStrategyResolver,
        embedding_factory: EmbeddingFactory,
        vector_search: RAGVectorSearchCapability,
        encryption_key: str,
    ) -> None:
        self._registry = registry
        self._embedding_factory = embedding_factory
        self._vector_search = vector_search
        self._encryption_key = encryption_key

    async def retrieve(
        self,
        *,
        binding: RAGBinding,
        query: str,
        history: tuple[Any, ...],
    ) -> RAGResult:
        try:
            strategy = self._registry.resolve(binding.strategy)
        except LookupError as exc:
            raise ValidationError(str(exc)) from exc

        capabilities = RAGCapabilities(
            embedding=RuntimeEmbeddingCapability(
                embedding_factory=self._embedding_factory,
                encryption_key=self._encryption_key,
                snapshot=binding.snapshot,
                provider_model=binding.provider_model,
                credential=binding.credential,
            ),
            vector_search=self._vector_search,
        )
        request = RAGRequest(
            query=query,
            history=history,
            config=binding.config,
            vector_snapshot_id=binding.snapshot.id,
            snapshot_documents=binding.snapshot_documents,
        )

        metadata = dict(binding.metadata)
        try:
            result = await strategy.retrieve(request, capabilities)
        except EmbeddingProviderError as exc:
            metadata.update(
                {
                    "failure_phase": "rag_query_embedding",
                    "embedding_error_category": exc.category,
                    "upstream_status": exc.upstream_status,
                    "upstream_error_code": exc.upstream_error_code,
                    "embedding_retryable": exc.retryable,
                }
            )
            setattr(exc, "rag_metadata", metadata)
            raise

        metadata.update(
            {
                key: value
                for key, value in result.metrics.items()
                if key not in metadata
            }
        )
        return RAGResult(
            context=result.context,
            sources=result.sources,
            metrics=metadata,
        )
