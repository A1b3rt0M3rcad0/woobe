from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.embedding_errors import (
    EmbeddingFailure,
    EmbeddingProviderError,
    normalize_embedding_error,
)
from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.rag import RAGBinding
from modules.agent.application.rag.registry import RAGStrategyRegistry
from modules.agent.application.rag.strategies.classic import ClassicRAGStrategy
from modules.agent.domain.entities import (
    Agent,
    KnowledgeVersion,
    ProviderCredential,
    ProviderModel,
)
from modules.agent.domain.enums import CredentialStatus, Provider, ProviderModelStatus
from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_READY,
    VectorSnapshot,
)
from modules.agent.infra.execution.rag import embedding_capability as embedding_module
from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter
from woobe_workers.consumers.agent.registry import AgentWorkerRegistry, register_agent_workers


class _OpenRouter402Error(RuntimeError):
    status_code = 402


class _UnusedVectorSearch:
    async def search(self, **_kwargs):
        raise AssertionError("vector search must not run when query embedding fails")


def test_embedding_402_is_normalized_without_raw_provider_payload():
    failure = normalize_embedding_error(
        _OpenRouter402Error(
            "Error code: 402 - {'error': {'message': 'Insufficient credits. secret payload'}}"
        )
    )

    assert failure.category == "provider_billing"
    assert failure.upstream_status == 402
    assert failure.upstream_error_code == "insufficient_credits"
    assert failure.retryable is False
    assert failure.safe_message == "Embedding provider account has insufficient credits."
    assert "secret payload" not in failure.safe_message


@pytest.mark.asyncio
async def test_rag_query_embedding_failure_records_terminal_metadata(monkeypatch):
    project_id = uuid4()
    agent_id = uuid4()
    knowledge_id = uuid4()
    credential_id = uuid4()
    provider_model_id = uuid4()

    agent = Agent(
        id=agent_id,
        project_id=project_id,
        name="Knowledge Agent",
        settings={
            "knowledge_version_id": str(knowledge_id),
            "runtime_config": {"rag": {}},
        },
    )
    knowledge = KnowledgeVersion(
        id=knowledge_id,
        project_id=project_id,
        agent_id=agent_id,
        version="v1",
        collection_ids=[uuid4()],
        snapshot_metadata={},
    )
    snapshot = VectorSnapshot(
        project_id=project_id,
        collection_id=knowledge.collection_ids[0],
        version="v1",
        embedding_provider_model_id=provider_model_id,
        embedding_provider="openrouter",
        embedding_model="openai/text-embedding-3-small",
        embedding_dimensions=1536,
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

    embedding_client = MagicMock()
    embedding_client.aembed_query = AsyncMock(
        side_effect=EmbeddingProviderError(
            EmbeddingFailure(
                category="provider_billing",
                safe_message="Embedding provider account has insufficient credits.",
                upstream_status=402,
                upstream_error_code="insufficient_credits",
                retryable=False,
            )
        )
    )
    embedding_factory = MagicMock()
    embedding_factory.create_embedding_client.return_value = embedding_client
    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "api-key")

    registry = RAGStrategyRegistry()
    registry.register("classic", ClassicRAGStrategy())
    adapter = RAGRuntimeAdapter(
        registry=registry,
        embedding_factory=embedding_factory,
        vector_search=_UnusedVectorSearch(),
        encryption_key="test-key",
    )

    rag_config = RAGRuntimeConfig()
    binding = RAGBinding(
        strategy=rag_config.strategy,
        config=rag_config,
        knowledge=knowledge,
        snapshot=snapshot,
        provider_model=provider_model,
        credential=credential,
        snapshot_documents=(),
        metadata={
            "strategy": rag_config.strategy,
            "knowledge_version_id": str(knowledge.id),
            "knowledge_version": knowledge.version,
            "vector_snapshot_id": str(snapshot.id),
            "vector_snapshot_version": snapshot.version,
            "snapshot_hash": snapshot.snapshot_hash,
            "embedding_provider_model_id": str(provider_model_id),
            "embedding_provider": snapshot.embedding_provider,
            "embedding_model": snapshot.embedding_model,
            "embedding_dimensions": snapshot.embedding_dimensions,
            "rag_runtime_config": rag_config.model_dump(),
            "rag_runtime_config_source": "production",
            "retrieval_query_mode": rag_config.query_mode,
        },
    )
    with pytest.raises(EmbeddingProviderError) as raised:
        await adapter.retrieve(
            binding=binding,
            query="What is in the knowledge base?",
            history=(),
        )

    assert str(raised.value) == "Embedding provider account has insufficient credits."
    metadata = getattr(raised.value, "rag_metadata")
    assert metadata["failure_phase"] == "rag_query_embedding"
    assert metadata["upstream_status"] == 402
    assert metadata["upstream_error_code"] == "insufficient_credits"
    assert metadata["embedding_error_category"] == "provider_billing"
    assert metadata["vector_snapshot_id"] == str(snapshot.id)
    assert metadata["embedding_provider_model_id"] == str(provider_model_id)


def test_database_pollers_are_registered_without_rabbitmq():
    registry = AgentWorkerRegistry()

    register_agent_workers(
        registry,
        settings=MagicMock(),
        engine=MagicMock(),
        rabbitmq_manager=None,
    )

    worker_names = {type(worker).__name__ for worker in registry.iter_workers()}
    assert "AskJobWorker" in worker_names
    assert "VectorSnapshotWorker" in worker_names
    assert "AgentOutboxDispatcherWorker" not in worker_names
