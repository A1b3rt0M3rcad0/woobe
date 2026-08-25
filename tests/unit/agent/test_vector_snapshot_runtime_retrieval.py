from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.application.use_cases.vector_snapshot_rag_mixin import VectorSnapshotRAGMixin
from modules.agent.domain.entities import Agent, KnowledgeVersion, ProviderCredential, ProviderModel
from modules.agent.domain.enums import CredentialStatus, Provider, ProviderModelStatus
from modules.agent.domain.vector_snapshot_entities import (
    VectorSnapshot,
    VectorSnapshotChunk,
    VectorSnapshotDocument,
    VECTOR_SNAPSHOT_READY,
)


class _BaseRuntime:
    def _apply_release_to_agent(self, agent, release):
        return agent

    def _apply_snapshot_override(self, agent, snapshot):
        return agent


class _RuntimeHost(VectorSnapshotRAGMixin, _BaseRuntime):
    _encryption_key = "test-key"


@pytest.mark.asyncio
async def test_vector_snapshot_rag_uses_agent_runtime_config_and_bound_snapshot(monkeypatch):
    project_id = uuid4()
    agent_id = uuid4()
    knowledge_id = uuid4()
    credential_id = uuid4()
    provider_model_id = uuid4()
    document_id = uuid4()
    rag_config = RAGRuntimeConfig(
        candidate_k=9,
        top_k=1,
        min_score=0.72,
        max_context_chunks=1,
        max_chunks_per_document=1,
        query_mode="current_message",
    )

    agent = Agent(
        id=agent_id,
        project_id=project_id,
        name="Contracts agent",
        settings={
            "knowledge_version_id": str(knowledge_id),
            "runtime_config": {"rag": rag_config.model_dump()},
        },
    )
    knowledge = KnowledgeVersion(
        id=knowledge_id,
        project_id=project_id,
        agent_id=agent_id,
        version="v2",
        collection_ids=[uuid4()],
        snapshot_metadata={},
    )
    snapshot = VectorSnapshot(
        project_id=project_id,
        collection_id=knowledge.collection_ids[0],
        version="v3",
        embedding_provider_model_id=provider_model_id,
        embedding_provider="openrouter",
        embedding_model="openai/text-embedding-3-small",
        embedding_dimensions=3,
        status=VECTOR_SNAPSHOT_READY,
        snapshot_hash="immutable-hash",
    )
    knowledge.snapshot_metadata = {"vector_snapshot_id": str(snapshot.id)}
    provider_model = ProviderModel(
        id=provider_model_id,
        project_id=project_id,
        provider_credential_id=credential_id,
        name="Embeddings",
        model=snapshot.embedding_model,
        status=ProviderModelStatus.active,
        metadata={"capability": "embedding"},
    )
    credential = ProviderCredential(
        id=credential_id,
        project_id=project_id,
        provider=Provider.openrouter,
        name="OpenRouter",
        encrypted_secret="encrypted",
        status=CredentialStatus.active,
    )
    chunk = VectorSnapshotChunk(
        vector_snapshot_id=snapshot.id,
        project_id=project_id,
        collection_id=snapshot.collection_id,
        document_id=document_id,
        content="The contract renewal date is 2031-04-17.",
        content_hash="chunk-hash",
        chunk_index=0,
        page_number=4,
    )
    snapshot_document = VectorSnapshotDocument(
        vector_snapshot_id=snapshot.id,
        document_id=document_id,
        document_sha256="doc-hash",
        document_title="Contract A",
        file_name="contract-a.pdf",
        parser="PDF",
        status_at_build="READY",
        chunk_count=1,
    )

    embedding_client = MagicMock()
    embedding_client.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embedding_factory = MagicMock()
    embedding_factory.create_embedding_client.return_value = embedding_client
    monkeypatch.setattr(
        "modules.agent.application.use_cases.vector_snapshot_rag_mixin.decrypt_secret",
        lambda *_args, **_kwargs: "api-key",
    )

    uow = MagicMock()
    uow.commit = AsyncMock()
    uow.knowledge_versions.get_by_id = AsyncMock(return_value=knowledge)
    uow.vector_snapshots.get_by_id = AsyncMock(return_value=snapshot)
    uow.vector_snapshots.search_similar = AsyncMock(return_value=[(chunk, 0.91)])
    uow.vector_snapshots.list_snapshot_documents = AsyncMock(return_value=[snapshot_document])
    uow.provider_models.get_by_id = AsyncMock(return_value=provider_model)
    uow.provider_credentials.get_by_id = AsyncMock(return_value=credential)

    host = _RuntimeHost()
    host.configure_rag_embedding_factory(embedding_factory)
    token = current_execution.set(new_execution_context())
    try:
        context, sources = await host._load_rag_context(agent, "When does it renew?", uow)
        execution_context = current_execution.get()
    finally:
        current_execution.reset(token)

    embedding_client.aembed_query.assert_awaited_once_with("When does it renew?")
    uow.commit.assert_awaited_once()
    uow.vector_snapshots.search_similar.assert_awaited_once_with(
        vector_snapshot_id=snapshot.id,
        embedding=[0.1, 0.2, 0.3],
        limit=9,
        threshold=0.0,
    )
    assert "2031-04-17" in context
    assert sources[0].document_title == "Contract A"
    assert sources[0].page_number == 4
    assert execution_context.rag_metadata["knowledge_version_id"] == str(knowledge.id)
    assert execution_context.rag_metadata["vector_snapshot_id"] == str(snapshot.id)
    assert execution_context.rag_metadata["snapshot_hash"] == "immutable-hash"
    assert execution_context.rag_metadata["rag_runtime_config"] == rag_config.model_dump()
    assert execution_context.rag_metadata["matched_chunks"] == 1


@pytest.mark.asyncio
async def test_vector_snapshot_rag_skips_retrieval_when_agent_has_no_knowledge():
    agent = Agent(project_id=uuid4(), settings={})
    context, sources = await _RuntimeHost()._load_rag_context(agent, "hello", MagicMock())
    assert context is None
    assert sources == []
