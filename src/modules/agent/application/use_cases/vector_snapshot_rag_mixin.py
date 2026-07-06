from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Protocol, cast
from uuid import UUID

from modules.agent.application.dtos.rag_config_dtos import (
    RAGRetrievalConfig,
    RAGRuntimeConfig,
)
from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.crypto import decrypt_secret
from shared.infra.errors import ValidationError


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


def _snapshot_defaults(raw: dict[str, Any]) -> RAGRetrievalConfig:
    normalized = dict(raw)
    if "min_score" not in normalized and "score_threshold" in normalized:
        normalized["min_score"] = normalized.get("score_threshold")
    normalized.pop("score_threshold", None)
    allowed = set(RAGRetrievalConfig.model_fields)
    return RAGRetrievalConfig.model_validate(
        {key: value for key, value in normalized.items() if key in allowed}
    )


def _runtime_overrides(agent: Any) -> tuple[dict[str, Any], RAGRuntimeConfig | None]:
    settings = _dict_value(getattr(agent, "settings", None))
    runtime_config = _dict_value(settings.get("runtime_config"))
    raw_rag = _dict_value(runtime_config.get("rag"))
    if not raw_rag:
        return {}, None
    try:
        return raw_rag, RAGRuntimeConfig.model_validate(raw_rag)
    except Exception as exc:
        raise ValidationError("Agent RAG runtime configuration is invalid") from exc


def _effective_config(
    snapshot_defaults: RAGRetrievalConfig,
    overrides: RAGRuntimeConfig | None,
) -> RAGRetrievalConfig:
    if overrides is None:
        return snapshot_defaults
    base = (
        snapshot_defaults.model_dump()
        if overrides.inherit_snapshot_defaults
        else RAGRetrievalConfig().model_dump()
    )
    values = overrides.model_dump(exclude_none=True)
    values.pop("inherit_snapshot_defaults", None)
    min_score_enabled = values.pop("min_score_enabled", None)
    if min_score_enabled is False:
        values["min_score"] = None
    base.update(values)
    return RAGRetrievalConfig.model_validate(base)


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
    """Resolve immutable KnowledgeVersion bindings into configurable retrieval."""

    _encryption_key: str
    _session_factory: Any

    async def _prepare(self, input_dto: Any) -> Any:
        history: list[Any] = []
        session_id = getattr(input_dto, "session_id", None)
        if session_id:
            try:
                async with AgentUnitOfWork(self._session_factory) as uow:
                    session = await uow.sessions.get_by_id(session_id)
                    if session is not None:
                        parent = cast(_VectorSnapshotRAGSuper, self)
                        history = await parent._load_history(uow.messages, session)
            except Exception:
                history = []
        token = _rag_history_context.set(history)
        try:
            parent = cast(_VectorSnapshotRAGSuper, super())
            return await parent._prepare(input_dto)
        finally:
            _rag_history_context.reset(token)

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

        knowledge_id = _uuid_value(
            knowledge_version_id,
            field_name="knowledge_version_id",
        )
        knowledge = await uow.knowledge_versions.get_by_id(knowledge_id)
        if knowledge is None:
            raise ValidationError("Configured KnowledgeVersion was not found")
        if knowledge.project_id != agent.project_id or knowledge.agent_id != agent.id:
            raise ValidationError(
                "Configured KnowledgeVersion does not belong to this Agent"
            )

        metadata = dict(knowledge.snapshot_metadata or {})
        vector_snapshot_id = metadata.get("vector_snapshot_id")
        if not vector_snapshot_id:
            raise ValidationError(
                "Configured KnowledgeVersion has no vector snapshot"
            )

        snapshot_id = _uuid_value(
            vector_snapshot_id,
            field_name="vector_snapshot_id",
        )
        snapshot = await uow.vector_snapshots.get_by_id(snapshot_id)
        if snapshot is None or snapshot.project_id != agent.project_id:
            raise ValidationError("Configured vector snapshot was not found")
        if snapshot.status != VECTOR_SNAPSHOT_READY:
            raise ValidationError("Configured vector snapshot is not READY")
        if not snapshot.snapshot_hash:
            raise ValidationError(
                "Configured vector snapshot has no immutable hash"
            )

        provider_model = await uow.provider_models.get_by_id(
            snapshot.embedding_provider_model_id
        )
        if provider_model is None or provider_model.project_id != agent.project_id:
            raise ValidationError("Embedding provider model was not found")
        if _status_value(provider_model.status) != ProviderModelStatus.active.value:
            raise ValidationError("Embedding provider model must be active")

        capability = str(
            (provider_model.metadata or {}).get("capability") or ""
        ).lower()
        if (
            capability not in {"embedding", "embeddings"}
            and "embed" not in provider_model.model.lower()
        ):
            raise ValidationError(
                "Configured provider model is not an embedding model"
            )

        credential = await uow.provider_credentials.get_by_id(
            provider_model.provider_credential_id
        )
        if credential is None or credential.project_id != agent.project_id:
            raise ValidationError("Embedding provider credential was not found")
        if _status_value(credential.status) != CredentialStatus.active.value:
            raise ValidationError("Embedding provider credential must be active")

        try:
            api_key = decrypt_secret(
                credential.encrypted_secret,
                self._encryption_key,
            )
        except Exception as exc:
            raise ValidationError(
                "Embedding provider credential could not be decrypted"
            ) from exc

        provider = snapshot.embedding_provider
        base_url = None
        if provider == "custom":
            base_url = (provider_model.metadata or {}).get("base_url") or (
                credential.metadata or {}
            ).get("base_url")
            if not base_url:
                raise ValidationError(
                    "Custom embedding provider requires base_url"
                )
        elif provider == "openrouter":
            base_url = (credential.metadata or {}).get("base_url") or (
                provider_model.metadata or {}
            ).get("base_url")

        snapshot_config = _snapshot_defaults(
            dict(snapshot.retrieval_defaults or {})
        )
        raw_overrides, overrides = _runtime_overrides(agent)
        effective = _effective_config(snapshot_config, overrides)
        retrieval_query = _build_retrieval_query(
            query,
            _rag_history_context.get(),
            query_mode=effective.query_mode,
            history_turns=effective.history_turns,
        )

        embedding_client = LangchainEmbeddingFactory().create_embedding_client(
            provider=provider,
            model=snapshot.embedding_model,
            api_key=api_key,
            base_url=str(base_url) if base_url else None,
            dimensions=snapshot.embedding_dimensions,
        )
        query_embedding = await embedding_client.aembed_query(retrieval_query)
        if len(query_embedding) != snapshot.embedding_dimensions:
            raise ValidationError(
                "Query embedding dimensions do not match snapshot: "
                f"expected {snapshot.embedding_dimensions}, "
                f"got {len(query_embedding)}"
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
            filtered = [
                (chunk, score)
                for chunk, score in candidates
                if float(score) >= effective.min_score
            ]

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
        snapshot_documents = (
            await uow.vector_snapshots.list_snapshot_documents(snapshot.id)
        )
        document_titles = {
            document.document_id: document.document_title
            for document in snapshot_documents
        }

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

        rag_metadata: dict[str, Any] = {
            "knowledge_version_id": str(knowledge.id),
            "knowledge_version": knowledge.version,
            "vector_snapshot_id": str(snapshot.id),
            "vector_snapshot_version": snapshot.version,
            "snapshot_hash": snapshot.snapshot_hash,
            "embedding_provider_model_id": str(
                snapshot.embedding_provider_model_id
            ),
            "embedding_provider": snapshot.embedding_provider,
            "embedding_model": snapshot.embedding_model,
            "embedding_dimensions": snapshot.embedding_dimensions,
            "snapshot_defaults": snapshot_config.model_dump(),
            "agent_overrides": raw_overrides,
            "effective_config": effective.model_dump(),
            "retrieval_query_mode": effective.query_mode,
            "candidate_count": len(candidates),
            "best_score": candidate_scores[0] if candidate_scores else None,
            "top_scores": candidate_scores[:10],
            "filtered_count": len(filtered),
            "matched_chunks": len(selected),
            "context_chunks": len(sources),
            "context_chars": context_chars,
        }
        execution_context = current_execution.get()
        if execution_context:
            execution_context.rag_metadata = rag_metadata

        if not context_chunks:
            if effective.grounding_policy == "required":
                raise ValidationError(
                    "No relevant information was found in the configured knowledge version"
                )
            return None, []
        return "\n\n".join(context_chunks), sources
