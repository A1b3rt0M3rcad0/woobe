from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Protocol, cast
from uuid import UUID

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.embedding_errors import EmbeddingProviderError
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
from modules.agent.application.interfaces.embedding_factory import EmbeddingFactory
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from shared.security.crypto import decrypt_secret
from shared.contracts.errors import ValidationError


_rag_history_context: ContextVar[list[Any]] = ContextVar("rag_history_context", default=[])


class _VectorSnapshotRAGSuper(Protocol):
    async def _prepare(self, input_dto: Any) -> Any: ...
    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]: ...
    def _apply_release_to_agent(self, agent: Any, release: Any) -> Any: ...
    def _apply_snapshot_override(self, agent: Any, snapshot: dict[str, Any]) -> Any: ...


def _status_value(value: object) -> object:
    return getattr(value, "value", value)


def _uuid_value(value: object, *, field_name: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field_name}") from exc


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
    execution_context = str(getattr(context, "execution_context", None) or "playground").lower()
    release_version = str(getattr(context, "agent_release_version", None) or "")
    if execution_context == "staging":
        return "staging"
    if execution_context == "production":
        return "production"
    if release_version and release_version != "draft":
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
    if not conversational:
        return query
    tail = conversational[-(history_turns * 2) :]
    lines = [f"{role}: {content}" for role, content in tail]
    lines.append(f"Current user message: {query}")
    return "\n".join(lines)


class VectorSnapshotRAGMixin:
    """Resolve immutable KnowledgeVersion bindings using Agent runtime retrieval config."""

    _encryption_key: str
    _embedding_factory: EmbeddingFactory | None = None

    def configure_rag_embedding_factory(self, embedding_factory: EmbeddingFactory) -> None:
        self._embedding_factory = embedding_factory

    async def _prepare(self, input_dto: Any) -> Any:
        token = _rag_history_context.set([])
        try:
            parent = cast(_VectorSnapshotRAGSuper, super())
            return await parent._prepare(input_dto)
        finally:
            _rag_history_context.reset(token)

    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]:
        parent = cast(_VectorSnapshotRAGSuper, super())
        history = await parent._load_history(message_repo, session)
        _rag_history_context.set(history)
        context = current_execution.get()
        if context is not None:
            context.project_id = getattr(session, "project_id", None)
            context.agent_id = getattr(session, "agent_id", None)
            context.session_id = getattr(session, "id", None)
        return history

    def _apply_release_to_agent(self, agent: Any, release: Any) -> Any:
        parent = cast(_VectorSnapshotRAGSuper, super())
        agent = parent._apply_release_to_agent(agent, release)
        settings = dict(agent.settings or {})
        if release.knowledge_version_id is None:
            settings.pop("knowledge_version_id", None)
        else:
            settings["knowledge_version_id"] = str(release.knowledge_version_id)
        if getattr(release, "runtime_config", None) is None:
            settings.pop("runtime_config", None)
        else:
            settings["runtime_config"] = dict(release.runtime_config)
        agent.settings = settings
        return agent

    def _apply_snapshot_override(self, agent: Any, snapshot: dict[str, Any]) -> Any:
        parent = cast(_VectorSnapshotRAGSuper, super())
        agent = parent._apply_snapshot_override(agent, snapshot)
        settings = dict(agent.settings or {})
        if "knowledge_version_id" in snapshot:
            value = snapshot.get("knowledge_version_id")
            if value:
                settings["knowledge_version_id"] = str(value)
            else:
                settings.pop("knowledge_version_id", None)
        if "runtime_config" in snapshot:
            runtime_config = snapshot.get("runtime_config")
            if isinstance(runtime_config, dict):
                settings["runtime_config"] = runtime_config
            else:
                settings.pop("runtime_config", None)
        agent.settings = settings
        return agent

    async def _load_rag_context(
        self,
        agent: Any,
        query: str,
        uow: Any,
    ) -> tuple[str | None, list[SourceInfo]]:
        settings = dict(agent.settings or {})
        knowledge_version_id = settings.get("knowledge_version_id")
        if not knowledge_version_id:
            context = current_execution.get()
            if context:
                context.rag_metadata = None
            return None, []

        knowledge_id = _uuid_value(knowledge_version_id, field_name="knowledge_version_id")
        knowledge = await uow.knowledge_versions.get_by_id(knowledge_id)
        if knowledge is None:
            raise ValidationError("Configured KnowledgeVersion was not found")
        if knowledge.project_id != agent.project_id or knowledge.agent_id != agent.id:
            raise ValidationError("Configured KnowledgeVersion does not belong to this Agent")

        metadata = dict(knowledge.snapshot_metadata or {})
        vector_snapshot_id = metadata.get("vector_snapshot_id")
        if not vector_snapshot_id:
            raise ValidationError("Configured KnowledgeVersion has no vector snapshot")

        snapshot_id = _uuid_value(vector_snapshot_id, field_name="vector_snapshot_id")
        snapshot = await uow.vector_snapshots.get_by_id(snapshot_id)
        if snapshot is None or snapshot.project_id != agent.project_id:
            raise ValidationError("Configured vector snapshot was not found")
        if snapshot.status != VECTOR_SNAPSHOT_READY:
            raise ValidationError("Configured vector snapshot is not READY")
        if not snapshot.snapshot_hash:
            raise ValidationError("Configured vector snapshot has no immutable hash")

        provider_model = await uow.provider_models.get_by_id(snapshot.embedding_provider_model_id)
        if provider_model is None or provider_model.project_id != agent.project_id:
            raise ValidationError("Embedding provider model was not found")
        if _status_value(provider_model.status) != ProviderModelStatus.active.value:
            raise ValidationError("Embedding provider model must be active")

        capability = str((provider_model.metadata or {}).get("capability") or "").lower()
        if capability not in {"embedding", "embeddings"} and "embed" not in provider_model.model.lower():
            raise ValidationError("Configured provider model is not an embedding model")

        credential = await uow.provider_credentials.get_by_id(provider_model.provider_credential_id)
        if credential is None or credential.project_id != agent.project_id:
            raise ValidationError("Embedding provider credential was not found")
        if _status_value(credential.status) != CredentialStatus.active.value:
            raise ValidationError("Embedding provider credential must be active")

        try:
            api_key = decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as exc:
            raise ValidationError("Embedding provider credential could not be decrypted") from exc

        provider = snapshot.embedding_provider
        base_url = None
        if provider == "custom":
            base_url = (provider_model.metadata or {}).get("base_url") or (credential.metadata or {}).get("base_url")
            if not base_url:
                raise ValidationError("Custom embedding provider requires base_url")
        elif provider == "openrouter":
            base_url = (credential.metadata or {}).get("base_url") or (provider_model.metadata or {}).get("base_url")

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
        execution_context = current_execution.get()
        if execution_context:
            execution_context.rag_metadata = dict(rag_metadata)

        if self._embedding_factory is None:
            raise ValidationError("RAG embedding runtime is not configured")

        # Session creation and the user's message happen before RAG in AskAgentUseCase.
        # Commit that admission state before crossing the external embedding boundary so
        # a provider failure does not make the user's submitted message disappear.
        commit = getattr(uow, "commit", None)
        if callable(commit):
            await commit()

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
            rag_metadata["failure_phase"] = "rag_query_embedding_validation"
            if execution_context:
                execution_context.rag_metadata = dict(rag_metadata)
            raise ValidationError(
                "Query embedding dimensions do not match snapshot: "
                f"expected {snapshot.embedding_dimensions}, got {len(query_embedding)}"
            )

        candidates = await uow.vector_snapshots.search_similar(
            vector_snapshot_id=snapshot.id,
            embedding=query_embedding,
            limit=effective.candidate_k,
            threshold=0.0,
        )
        candidate_scores = [round(float(score), 4) for _, score in candidates]
        if effective.min_score is None:
            filtered = candidates
        else:
            filtered = [(chunk, score) for chunk, score in candidates if float(score) >= effective.min_score]

        selected: list[tuple[Any, float]] = []
        per_document: dict[UUID, int] = {}
        for chunk, score in filtered:
            document_count = per_document.get(chunk.document_id, 0)
            if document_count >= effective.max_chunks_per_document:
                continue
            selected.append((chunk, score))
            per_document[chunk.document_id] = document_count + 1
            if len(selected) >= effective.top_k:
                break

        context_results = selected[: effective.max_context_chunks]
        snapshot_documents = await uow.vector_snapshots.list_snapshot_documents(snapshot.id)
        document_titles = {document.document_id: document.document_title for document in snapshot_documents}

        sources: list[SourceInfo] = []
        context_chunks: list[str] = []
        context_chars = 0
        for chunk, score in context_results:
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
                raise ValidationError("No relevant information was found in the configured knowledge version")
            return None, []
        return "\n\n".join(context_chunks), sources
