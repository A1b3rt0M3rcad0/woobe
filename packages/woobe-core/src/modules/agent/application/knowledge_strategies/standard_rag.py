from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.embedding_errors import EmbeddingProviderError
from modules.agent.application.interfaces.knowledge_strategy import (
    KnowledgePreparationRequest,
    KnowledgePreparedBinding,
    KnowledgeRetrievalOutput,
    KnowledgeRetrievalRequest,
    STANDARD_RAG_STRATEGY_KEY,
)
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from shared.contracts.errors import ValidationError
from shared.security.crypto import decrypt_secret


def _value(value: object) -> object:
    return getattr(value, "value", value)


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


class StandardVectorRAGStrategy:
    """The original Woobe immutable Vector Snapshot RAG as ``std-rag:v1``."""

    async def prepare(
        self,
        request: KnowledgePreparationRequest,
    ) -> KnowledgePreparedBinding | None:
        agent = request.agent
        resources = request.resources
        settings = dict(agent.settings or {})
        knowledge_version_id = settings.get("knowledge_version_id")
        if not knowledge_version_id:
            return None

        try:
            knowledge_id = (
                knowledge_version_id
                if isinstance(knowledge_version_id, UUID)
                else UUID(str(knowledge_version_id))
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("Invalid knowledge_version_id") from exc

        knowledge = await resources.knowledge_versions.get_by_id(knowledge_id)
        if knowledge is None:
            raise ValidationError("Configured KnowledgeVersion was not found")
        if knowledge.project_id != agent.project_id or knowledge.agent_id != agent.id:
            raise ValidationError("Configured KnowledgeVersion does not belong to this Agent")

        metadata = dict(knowledge.snapshot_metadata or {})
        vector_snapshot_id = metadata.get("vector_snapshot_id")
        if not vector_snapshot_id:
            raise ValidationError("Configured KnowledgeVersion has no vector snapshot")
        try:
            snapshot_id = (
                vector_snapshot_id
                if isinstance(vector_snapshot_id, UUID)
                else UUID(str(vector_snapshot_id))
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError("Invalid vector_snapshot_id") from exc

        snapshot = await resources.vector_snapshots.get_by_id(snapshot_id)
        if snapshot is None or snapshot.project_id != agent.project_id:
            raise ValidationError("Configured vector snapshot was not found")
        if snapshot.status != VECTOR_SNAPSHOT_READY:
            raise ValidationError("Configured vector snapshot is not READY")
        if not snapshot.snapshot_hash:
            raise ValidationError("Configured vector snapshot has no immutable hash")

        provider_model = await resources.provider_models.get_by_id(
            snapshot.embedding_provider_model_id
        )
        if provider_model is None or provider_model.project_id != agent.project_id:
            raise ValidationError("Embedding provider model was not found")
        if _value(provider_model.status) != ProviderModelStatus.active.value:
            raise ValidationError("Embedding provider model must be active")
        capability = str((provider_model.metadata or {}).get("capability") or "").lower()
        if (
            capability not in {"embedding", "embeddings"}
            and "embed" not in provider_model.model.lower()
        ):
            raise ValidationError("Configured provider model is not an embedding model")

        credential = await resources.provider_credentials.get_by_id(
            provider_model.provider_credential_id
        )
        if credential is None or credential.project_id != agent.project_id:
            raise ValidationError("Embedding provider credential was not found")
        if _value(credential.status) != CredentialStatus.active.value:
            raise ValidationError("Embedding provider credential must be active")

        snapshot_documents = await resources.vector_snapshots.list_snapshot_documents(
            snapshot.id
        )
        runtime_state = {
            "knowledge": knowledge,
            "snapshot": snapshot,
            "provider_model": provider_model,
            "credential": credential,
            "snapshot_documents": snapshot_documents,
        }
        execution_snapshot = {
            "knowledge_version_id": str(knowledge.id),
            "knowledge_version": knowledge.version,
            "strategy": STANDARD_RAG_STRATEGY_KEY.as_dict(),
            "artifacts": [
                {
                    "kind": "vector_snapshot",
                    "id": str(snapshot.id),
                    "version": snapshot.version,
                    "hash": snapshot.snapshot_hash,
                    "embedding_provider_model_id": str(
                        snapshot.embedding_provider_model_id
                    ),
                    "embedding_provider": snapshot.embedding_provider,
                    "embedding_model": snapshot.embedding_model,
                    "embedding_dimensions": snapshot.embedding_dimensions,
                }
            ],
        }
        return KnowledgePreparedBinding(
            strategy_key=STANDARD_RAG_STRATEGY_KEY,
            runtime_state=runtime_state,
            snapshot=execution_snapshot,
        )

    async def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
    ) -> KnowledgeRetrievalOutput:
        state = request.binding.runtime_state
        if not isinstance(state, dict):
            raise ValidationError("Standard RAG binding is invalid")

        knowledge = state["knowledge"]
        snapshot = state["snapshot"]
        provider_model = state["provider_model"]
        credential = state["credential"]
        snapshot_documents = state["snapshot_documents"]

        try:
            api_key = decrypt_secret(credential.encrypted_secret, request.encryption_key)
        except Exception as exc:
            raise ValidationError(
                "Embedding provider credential could not be decrypted"
            ) from exc

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

        effective = _runtime_config(request.agent)
        retrieval_query = _build_retrieval_query(
            request.query,
            request.history,
            query_mode=effective.query_mode,
            history_turns=effective.history_turns,
        )
        metadata: dict[str, Any] = {
            "strategy_name": request.binding.strategy_key.name,
            "strategy_version": request.binding.strategy_key.version,
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
            "rag_runtime_config_source": request.runtime_config_source,
            "retrieval_query_mode": effective.query_mode,
        }

        if request.embedding_factory is None:
            raise ValidationError("RAG embedding runtime is not configured")
        if request.vector_search_reader is None:
            raise ValidationError("RAG vector search runtime is not configured")

        try:
            embedding_client = request.embedding_factory.create_embedding_client(
                provider=provider,
                model=snapshot.embedding_model,
                api_key=api_key,
                base_url=str(base_url) if base_url else None,
                dimensions=snapshot.embedding_dimensions,
            )
            query_embedding = await embedding_client.aembed_query(retrieval_query)
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
            raise

        if len(query_embedding) != snapshot.embedding_dimensions:
            metadata["failure_phase"] = "rag_query_embedding_validation"
            raise ValidationError(
                "Query embedding dimensions do not match snapshot: "
                f"expected {snapshot.embedding_dimensions}, got {len(query_embedding)}"
            )

        candidates = await request.vector_search_reader(
            vector_snapshot_id=snapshot.id,
            embedding=query_embedding,
            limit=effective.candidate_k,
            threshold=0.0,
        )
        candidate_scores = [round(float(score), 4) for _, score in candidates]
        filtered = (
            candidates
            if effective.min_score is None
            else [
                (chunk, score)
                for chunk, score in candidates
                if float(score) >= effective.min_score
            ]
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
            document.document_id: document.document_title
            for document in snapshot_documents
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

        metadata.update(
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
        if not context_chunks:
            if effective.grounding_policy == "required":
                raise ValidationError(
                    "No relevant information was found in the configured knowledge version"
                )
            return KnowledgeRetrievalOutput(
                context=None,
                sources=[],
                metadata=metadata,
            )
        return KnowledgeRetrievalOutput(
            context="\n\n".join(context_chunks),
            sources=sources,
            metadata=metadata,
        )
