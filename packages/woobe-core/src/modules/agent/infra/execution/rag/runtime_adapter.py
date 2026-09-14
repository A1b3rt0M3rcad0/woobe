from __future__ import annotations

from typing import Any

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.embedding_errors import EmbeddingProviderError
from modules.agent.application.interfaces.embedding_factory import EmbeddingFactory
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.rag import (
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


def _dict_value(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _runtime_config(agent: Any) -> RAGRuntimeConfig:
    settings = _dict_value(getattr(agent, "settings", None))
    runtime_config = _dict_value(settings.get("runtime_config"))
    raw_rag = _dict_value(runtime_config.get("rag"))
    try:
        return RAGRuntimeConfig.model_validate(raw_rag)
    except Exception as exc:
        raise ValidationError("Agent RAG runtime configuration is invalid") from exc


def _runtime_config_source() -> str:
    context = current_execution.get()
    if context is None:
        return "draft"
    execution_context = str(context.execution_context or "playground").lower()
    if execution_context == "staging":
        return "staging"
    if execution_context == "production":
        return "production"
    if context.agent_release_version and context.agent_release_version != "draft":
        return "loaded_release"
    return "draft"


class RAGRuntimeAdapter:
    """Connect frozen Woobe runtime state to a selected RAG strategy."""

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
        agent: Any,
        query: str,
        history: tuple[Any, ...],
    ) -> RAGResult:
        settings = _dict_value(getattr(agent, "settings", None))
        if not settings.get("knowledge_version_id"):
            context = current_execution.get()
            if context is not None:
                context.rag_metadata = None
            return RAGResult(context=None)

        execution_context = current_execution.get()
        prepared = execution_context.prepared_rag if execution_context else None
        if not prepared:
            raise ValidationError("RAG binding was not prepared during Agent Run acceptance")

        knowledge = prepared["knowledge"]
        snapshot = prepared["snapshot"]
        provider_model = prepared["provider_model"]
        credential = prepared["credential"]
        snapshot_documents = tuple(prepared["snapshot_documents"])
        effective = _runtime_config(agent)

        try:
            strategy = self._registry.resolve(effective.strategy)
        except LookupError as exc:
            raise ValidationError(str(exc)) from exc

        rag_metadata: dict[str, Any] = {
            "strategy": effective.strategy,
            "knowledge_version_id": str(knowledge.id),
            "knowledge_version": knowledge.version,
            "vector_snapshot_id": str(snapshot.id),
            "vector_snapshot_version": snapshot.version,
            "snapshot_hash": snapshot.snapshot_hash,
            "embedding_provider_model_id": str(snapshot.embedding_provider_model_id),
            "embedding_provider": snapshot.embedding_provider,
            "embedding_model": snapshot.embedding_model,
            "embedding_dimensions": snapshot.embedding_dimensions,
            "rag_runtime_config": effective.model_dump(),
            "rag_runtime_config_source": _runtime_config_source(),
            "retrieval_query_mode": effective.query_mode,
        }
        if execution_context is not None:
            execution_context.rag_metadata = dict(rag_metadata)

        capabilities = RAGCapabilities(
            embedding=RuntimeEmbeddingCapability(
                embedding_factory=self._embedding_factory,
                encryption_key=self._encryption_key,
                snapshot=snapshot,
                provider_model=provider_model,
                credential=credential,
            ),
            vector_search=self._vector_search,
        )
        request = RAGRequest(
            query=query,
            history=history,
            config=effective,
            vector_snapshot_id=snapshot.id,
            snapshot_documents=snapshot_documents,
        )

        try:
            result = await strategy.retrieve(request, capabilities)
        except EmbeddingProviderError as exc:
            rag_metadata.update(
                {
                    "failure_phase": "rag_query_embedding",
                    "embedding_error_category": exc.category,
                    "upstream_status": exc.upstream_status,
                    "upstream_error_code": exc.upstream_error_code,
                    "embedding_retryable": exc.retryable,
                }
            )
            if execution_context is not None:
                execution_context.rag_metadata = dict(rag_metadata)
            raise

        for key, value in result.metrics.items():
            if key not in rag_metadata:
                rag_metadata[key] = value
        if execution_context is not None:
            execution_context.rag_metadata = rag_metadata
        return result
