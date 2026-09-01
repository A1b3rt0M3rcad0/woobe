from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Protocol, cast
from uuid import UUID

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.embedding_errors import EmbeddingProviderError
from modules.agent.application.interfaces.execution_context import current_execution
from shared.contracts.errors import ValidationError
from shared.security.crypto import decrypt_secret

_rag_history_context: ContextVar[list[Any]] = ContextVar(
    "transaction_bounded_rag_history_context",
    default=[],
)
VectorSearchReader = Callable[..., Awaitable[list[tuple[Any, float]]]]


class _RAGSuper(Protocol):
    async def _prepare(self, input_dto: Any) -> Any: ...
    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]: ...


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


def _build_retrieval_query(
    query: str,
    history: list[Any],
    *,
    query_mode: str,
    history_turns: int,
) -> str:
    if query_mode != "conversation_context" or not history:
        return query
    conversational: list[tuple[str, str]] = []
    for message in history:
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            continue
        class_name = type(message).__name__
        if class_name == "HumanMessage":
            conversational.append(("User", content.strip()))
        elif class_name == "AIMessage":
            conversational.append(("Assistant", content.strip()))
    tail = conversational[-(history_turns * 2) :]
    if not tail:
        return query
    lines = [f"{role}: {content}" for role, content in tail]
    lines.append(f"Current user message: {query}")
    return "\n".join(lines)


class TransactionBoundedVectorSnapshotRAGMixin:
    """RAG executes external embedding + one short read-only vector query."""

    _encryption_key: str
    _embedding_factory: Any
    _vector_search_reader: VectorSearchReader | None = None

    def configure_vector_search_reader(self, reader: VectorSearchReader) -> None:
        self._vector_search_reader = reader

    async def _prepare(self, input_dto: Any) -> Any:
        token = _rag_history_context.set([])
        try:
            parent = cast(_RAGSuper, super())
            return await parent._prepare(input_dto)
        finally:
            _rag_history_context.reset(token)

    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]:
        parent = cast(_RAGSuper, super())
        history = await parent._load_history(message_repo, session)
        _rag_history_context.set(history)
        return history

    async def _load_rag_context(
        self,
        agent: Any,
        query: str,
        transactions: Any,
    ) -> tuple[str | None, list[SourceInfo]]:
        del transactions
        settings = dict(agent.settings or {})
        if not settings.get("knowledge_version_id"):
            context = current_execution.get()
            if context:
                context.rag_metadata = None
            return None, []

        execution_context = current_execution.get()
        prepared = execution_context.prepared_rag if execution_context else None
        if not prepared:
            raise ValidationError("RAG binding was not prepared during Agent Run acceptance")

        knowledge = prepared["knowledge"]
        snapshot = prepared["snapshot"]
        provider_model = prepared["provider_model"]
        credential = prepared["credential"]
        snapshot_documents = prepared["snapshot_documents"]

        try:
            api_key = decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as exc:
            raise ValidationError("Embedding provider credential could not be decrypted") from exc

        provider = snapshot.embedding_provider
        base_url = None
        if provider == "custom":
            base_url = (
                (provider_model.metadata or {}).get("base_url")
                or (credential.metadata or {}).get("base_url")
            )
            if not base_url:
                raise ValidationError("Custom embedding provider requires base_url")
        elif provider == "openrouter":
            base_url = (
                (credential.metadata or {}).get("base_url")
                or (provider_model.metadata or {}).get("base_url")
            )

        effective = _runtime_config(agent)
        retrieval_query = _build_retrieval_query(
            query,
            _rag_history_context.get(),
            query_mode=effective.query_mode,
            history_turns=effective.history_turns,
        )
        rag_metadata: dict[str, Any] = {
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
        if execution_context:
            execution_context.rag_metadata = dict(rag_metadata)

        if self._embedding_factory is None:
            raise ValidationError("RAG embedding runtime is not configured")
        try:
            embedding_client = self._embedding_factory.create_embedding_client(
                provider=provider,
                model=snapshot.embedding_model,
                api_key=api_key,
                base_url=str(base_url) if base_url else None,
                dimensions=snapshot.embedding_dimensions,
            )
            query_embedding = await embedding_client.aembed_query(retrieval_query)
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
            if execution_context:
                execution_context.rag_metadata = dict(rag_metadata)
            raise

        if len(query_embedding) != snapshot.embedding_dimensions:
            raise ValidationError(
                "Query embedding dimensions do not match snapshot: "
                f"expected {snapshot.embedding_dimensions}, got {len(query_embedding)}"
            )
        if self._vector_search_reader is None:
            raise ValidationError("RAG vector search runtime is not configured")

        candidates = await self._vector_search_reader(
            vector_snapshot_id=snapshot.id,
            embedding=query_embedding,
            limit=effective.candidate_k,
            threshold=0.0,
        )
        candidate_scores = [round(float(score), 4) for _, score in candidates]
        filtered = (
            candidates
            if effective.min_score is None
            else [(chunk, score) for chunk, score in candidates if float(score) >= effective.min_score]
        )

        selected: list[tuple[Any, float]] = []
        per_document: dict[UUID, int] = {}
        for chunk, score in filtered:
            count = per_document.get(chunk.document_id, 0)
            if count >= effective.max_chunks_per_document:
                continue
            selected.append((chunk, score))
            per_document[chunk.document_id] = count + 1
            if len(selected) >= effective.top_k:
                break

        document_titles = {
            document.document_id: document.document_title for document in snapshot_documents
        }
        sources: list[SourceInfo] = []
        context_chunks: list[str] = []
        context_chars = 0
        for chunk, score in selected[: effective.max_context_chunks]:
            title = document_titles.get(chunk.document_id)
            prefix = f"[{len(context_chunks) + 1}]"
            if title:
                prefix += f" {title}"
            if chunk.page_number is not None:
                prefix += f" · page {chunk.page_number}"
            block = f"{prefix}\n{chunk.content}"
            remaining = effective.max_context_chars - context_chars
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = block[:remaining]
            context_chunks.append(block)
            context_chars += len(block)
            sources.append(
                SourceInfo(
                    document_id=str(chunk.document_id),
                    document_title=title,
                    chunk_id=str(chunk.id),
                    page_number=chunk.page_number,
                    score=round(float(score), 4),
                    content_preview=chunk.content[:200],
                )
            )

        rag_metadata.update(
            {
                "candidate_count": len(candidates),
                "best_score": candidate_scores[0] if candidate_scores else None,
                "top_scores": candidate_scores[:10],
                "filtered_count": len(filtered),
                "matched_chunks": len(selected),
                "context_chunks": len(sources),
                "context_chars": context_chars,
            }
        )
        if execution_context:
            execution_context.rag_metadata = rag_metadata
        if not context_chunks:
            if effective.grounding_policy == "required":
                raise ValidationError(
                    "No relevant information was found in the configured knowledge version"
                )
            return None, []
        return "\n\n".join(context_chunks), sources
