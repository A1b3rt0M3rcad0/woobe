from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.use_cases.execution_context import current_execution
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from shared.infra.crypto import decrypt_secret
from shared.infra.errors import ValidationError


_MAX_RETRIEVAL_TOP_K = 20
_MAX_CONTEXT_CHARS = 24_000


def _status_value(value: object) -> object:
    return getattr(value, "value", value)


def _uuid_value(value: object, *, field_name: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid {field_name}") from exc


class VectorSnapshotRAGMixin:
    """Resolve immutable KnowledgeVersion bindings into vector retrieval context."""

    def _apply_release_to_agent(self, agent, release):
        agent = super()._apply_release_to_agent(agent, release)
        settings = dict(agent.settings or {})
        if release.knowledge_version_id is None:
            settings.pop("knowledge_version_id", None)
        else:
            settings["knowledge_version_id"] = str(release.knowledge_version_id)
        agent.settings = settings
        return agent

    def _apply_snapshot_override(self, agent, snapshot: dict):
        agent = super()._apply_snapshot_override(agent, snapshot)
        if "knowledge_version_id" in snapshot:
            settings = dict(agent.settings or {})
            value = snapshot.get("knowledge_version_id")
            if value:
                settings["knowledge_version_id"] = str(value)
            else:
                settings.pop("knowledge_version_id", None)
            agent.settings = settings
        return agent

    async def _load_rag_context(self, agent, query: str, uow) -> tuple[str | None, list[SourceInfo]]:
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

        embedding_client = LangchainEmbeddingFactory().create_embedding_client(
            provider=provider,
            model=snapshot.embedding_model,
            api_key=api_key,
            base_url=str(base_url) if base_url else None,
            dimensions=snapshot.embedding_dimensions,
        )
        query_embedding = await embedding_client.aembed_query(query)
        if len(query_embedding) != snapshot.embedding_dimensions:
            raise ValidationError(
                f"Query embedding dimensions do not match snapshot: expected {snapshot.embedding_dimensions}, got {len(query_embedding)}"
            )

        retrieval_defaults = dict(snapshot.retrieval_defaults or {})
        try:
            top_k = int(retrieval_defaults.get("top_k", 5))
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(top_k, _MAX_RETRIEVAL_TOP_K))
        try:
            threshold = float(retrieval_defaults.get("score_threshold", 0.7))
        except (TypeError, ValueError):
            threshold = 0.7
        threshold = max(0.0, min(threshold, 1.0))

        results = await uow.vector_snapshots.search_similar(
            vector_snapshot_id=snapshot.id,
            embedding=query_embedding,
            limit=top_k,
            threshold=threshold,
        )
        snapshot_documents = await uow.vector_snapshots.list_snapshot_documents(snapshot.id)
        document_titles = {document.document_id: document.document_title for document in snapshot_documents}

        sources: list[SourceInfo] = []
        context_chunks: list[str] = []
        context_chars = 0
        for chunk, score in results:
            title = document_titles.get(chunk.document_id)
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
            prefix = f"[{len(sources)}]"
            if title:
                prefix += f" {title}"
            if chunk.page_number is not None:
                prefix += f" · page {chunk.page_number}"
            block = f"{prefix}\n{chunk.content}"
            remaining = _MAX_CONTEXT_CHARS - context_chars
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = block[:remaining]
            context_chunks.append(block)
            context_chars += len(block)

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
            "retrieval_top_k": top_k,
            "retrieval_score_threshold": threshold,
            "matched_chunks": len(sources),
        }
        execution_context = current_execution.get()
        if execution_context:
            execution_context.rag_metadata = rag_metadata

        if not context_chunks:
            return None, sources
        return "\n\n".join(context_chunks), sources
