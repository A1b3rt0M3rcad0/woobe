from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.knowledge_release_validator import KnowledgeReleaseValidator
from modules.agent.domain.entities import KnowledgeVersion
from modules.agent.domain.enums import KnowledgeVersionStatus
from modules.agent.domain.vector_snapshot_entities import VectorSnapshot, VECTOR_SNAPSHOT_BUILDING, VECTOR_SNAPSHOT_READY
from shared.infra.errors import ValidationError


def make_case(status: str, snapshot_hash: str | None):
    project_id = uuid4()
    agent_id = uuid4()
    snapshot = VectorSnapshot(
        project_id=project_id,
        collection_id=uuid4(),
        version="v1",
        embedding_provider_model_id=uuid4(),
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        status=status,
        snapshot_hash=snapshot_hash,
    )
    knowledge = KnowledgeVersion(
        project_id=project_id,
        agent_id=agent_id,
        version="v1",
        collection_ids=[snapshot.collection_id],
        snapshot_metadata={"vector_snapshot_id": str(snapshot.id)},
        status=KnowledgeVersionStatus.DRAFT,
    )
    release = SimpleNamespace(project_id=project_id, agent_id=agent_id, knowledge_version_id=knowledge.id)
    knowledge_repo = AsyncMock()
    knowledge_repo.get_by_id.return_value = knowledge
    snapshot_repo = AsyncMock()
    snapshot_repo.get_by_id.return_value = snapshot
    return release, KnowledgeReleaseValidator(knowledge_repo, snapshot_repo)


@pytest.mark.asyncio
async def test_knowledge_release_validator_accepts_ready_snapshot():
    release, validator = make_case(VECTOR_SNAPSHOT_READY, "hash")
    await validator.validate(release)


@pytest.mark.asyncio
async def test_knowledge_release_validator_blocks_building_snapshot():
    release, validator = make_case(VECTOR_SNAPSHOT_BUILDING, None)
    with pytest.raises(ValidationError, match="READY"):
        await validator.validate(release)


@pytest.mark.asyncio
async def test_pending_knowledge_is_structural_only_and_never_release_ready():
    release, validator = make_case("PENDING_PREPARATION", None)
    with pytest.raises(ValidationError, match="READY"):
        await validator.validate(release)
    structural = KnowledgeReleaseValidator(validator._knowledge_version_repo, validator._vector_snapshot_repo, allow_pending=True)
    await structural.validate(release)
    snapshot = validator._vector_snapshot_repo.get_by_id.return_value
    snapshot.project_id = uuid4()
    with pytest.raises(ValidationError, match="Project"):
        await structural.validate(release)
