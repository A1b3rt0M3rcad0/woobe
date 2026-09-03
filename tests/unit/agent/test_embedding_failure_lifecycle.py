from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.embedding_errors import (
    EmbeddingFailure,
    EmbeddingProviderError,
    normalize_embedding_error,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.use_cases.vector_snapshot_rag_mixin import (
    VectorSnapshotRAGMixin,
)
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
from woobe_workers.consumers.agent.registry import AgentWorkerRegistry, register_agent_workers


class _OpenRouter402Error(RuntimeError):
    status_code = 402


class _BaseRuntime:
    def _apply_release_to_agent(self, agent, release):
        return agent

    def _apply_snapshot_override(self, agent, snapshot):
        return agent


class _RuntimeHost(VectorSnapshotRAGMixin, _BaseRuntime):
    _encryption_key = "test-key"


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
    monkeypatch.setattr(
        "modules.agent.application.use_cases.vector_snapshot_rag_mixin.decrypt_secret",
        lambda *_args, **_kwargs: "api-key",
    )

    uow = MagicMock()
    uow.commit = AsyncMock()
    uow.knowledge_versions.get_by_id = AsyncMock(return_value=knowledge)
    uow.vector_snapshots.get_by_id = AsyncMock(return_value=snapshot)
    uow.provider_models.get_by_id = AsyncMock(return_value=provider_model)
    uow.provider_credentials.get_by_id = AsyncMock(return_value=credential)

    host = _RuntimeHost()
    host.configure_rag_embedding_factory(embedding_factory)
    token = current_execution.set(new_execution_context())
    try:
        with pytest.raises(EmbeddingProviderError) as raised:
            await host._load_rag_context(agent, "What is in the knowledge base?", uow)
        execution_context = current_execution.get()
    finally:
        current_execution.reset(token)

    assert str(raised.value) == "Embedding provider account has insufficient credits."
    uow.commit.assert_awaited_once()
    assert execution_context is not None
    assert execution_context.rag_metadata["failure_phase"] == "rag_query_embedding"
    assert execution_context.rag_metadata["upstream_status"] == 402
    assert execution_context.rag_metadata["upstream_error_code"] == "insufficient_credits"
    assert execution_context.rag_metadata["embedding_error_category"] == "provider_billing"
    assert execution_context.rag_metadata["vector_snapshot_id"] == str(snapshot.id)
    assert execution_context.rag_metadata["embedding_provider_model_id"] == str(provider_model_id)


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
