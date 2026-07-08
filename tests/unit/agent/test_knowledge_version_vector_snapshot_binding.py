from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.knowledge_dtos import CreateKnowledgeVersionInput
from modules.agent.application.use_cases.knowledge_use_cases import CreateKnowledgeVersionUseCase
from modules.agent.domain.entities import Agent, KnowledgeVersion
from modules.agent.domain.enums import KnowledgeVersionStatus
from modules.agent.domain.vector_snapshot_entities import VectorSnapshot, VECTOR_SNAPSHOT_READY


@pytest.mark.asyncio
async def test_create_knowledge_version_binds_ready_snapshot_and_generates_version():
    project_id = uuid4()
    agent_id = uuid4()
    snapshot = VectorSnapshot(
        project_id=project_id,
        collection_id=uuid4(),
        version="v3",
        embedding_provider_model_id=uuid4(),
        embedding_provider="openrouter",
        embedding_model="openai/text-embedding-3-small",
        status=VECTOR_SNAPSHOT_READY,
        snapshot_hash="snapshot-hash",
        document_count=2,
        chunk_count=18,
    )

    repo = AsyncMock()
    repo.list_by_agent.return_value = []
    repo.get_by_version.return_value = None
    repo.save.side_effect = lambda entity: entity
    snapshot_repo = AsyncMock()
    snapshot_repo.get_by_id.return_value = snapshot
    agent_repo = AsyncMock()
    agent_repo.get_by_id.return_value = Agent(id=agent_id, project_id=project_id)

    use_case = CreateKnowledgeVersionUseCase(repo, snapshot_repo, agent_repo)
    result = await use_case.execute(
        CreateKnowledgeVersionInput(
            project_id=project_id,
            agent_id=agent_id,
            snapshot_metadata={"vector_snapshot_id": str(snapshot.id)},
        )
    )

    assert result.version == "v1"
    assert result.collection_ids == [snapshot.collection_id]
    assert result.snapshot_metadata["vector_snapshot_id"] == str(snapshot.id)
    assert result.snapshot_metadata["vector_snapshot_version"] == "v3"
    assert result.snapshot_metadata["snapshot_hash"] == "snapshot-hash"
    assert "retrieval_defaults" not in result.snapshot_metadata
    repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_knowledge_version_reuses_existing_binding_for_same_snapshot():
    project_id = uuid4()
    agent_id = uuid4()
    snapshot = VectorSnapshot(
        project_id=project_id,
        collection_id=uuid4(),
        version="v1",
        embedding_provider_model_id=uuid4(),
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        status=VECTOR_SNAPSHOT_READY,
        snapshot_hash="hash",
    )
    existing = KnowledgeVersion(
        project_id=project_id,
        agent_id=agent_id,
        version="v1",
        collection_ids=[snapshot.collection_id],
        snapshot_metadata={"vector_snapshot_id": str(snapshot.id)},
        status=KnowledgeVersionStatus.DRAFT,
    )

    repo = AsyncMock()
    repo.list_by_agent.return_value = [existing]
    snapshot_repo = AsyncMock()
    snapshot_repo.get_by_id.return_value = snapshot
    agent_repo = AsyncMock()
    agent_repo.get_by_id.return_value = Agent(id=agent_id, project_id=project_id)

    use_case = CreateKnowledgeVersionUseCase(repo, snapshot_repo, agent_repo)
    result = await use_case.execute(
        CreateKnowledgeVersionInput(
            project_id=project_id,
            agent_id=agent_id,
            snapshot_metadata={"vector_snapshot_id": str(snapshot.id)},
        )
    )

    assert result.id == existing.id
    repo.save.assert_not_awaited()
