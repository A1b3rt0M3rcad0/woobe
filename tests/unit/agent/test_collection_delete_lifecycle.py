from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.knowledge_dtos import UpdateCollectionInput
from modules.agent.application.use_cases.update_collection_use_case import (
    UpdateCollectionUseCase,
)
from modules.agent.domain.enums import CollectionStatus
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
async def test_collection_delete_is_blocked_while_attached_to_agent() -> None:
    collection_id = uuid4()
    project_id = uuid4()
    collection = SimpleNamespace(
        id=collection_id,
        project_id=project_id,
        name="Knowledge",
        description=None,
        status=CollectionStatus.ACTIVE,
        created_at=None,
        updated_at=None,
    )
    collection_repo = AsyncMock()
    collection_repo.get_by_id.return_value = collection
    collection_repo.update.return_value = collection
    agent_collection_repo = AsyncMock()
    agent_collection_repo.list_by_collection.return_value = [
        SimpleNamespace(id=uuid4())
    ]
    use_case = UpdateCollectionUseCase(
        collection_repo,
        agent_collection_repo,
    )

    with pytest.raises(ConflictError, match="still attached"):
        await use_case.execute(
            UpdateCollectionInput(
                collection_id=collection_id,
                status=CollectionStatus.DELETED,
            )
        )

    collection_repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_collection_delete_soft_deletes_when_unattached() -> None:
    collection_id = uuid4()
    project_id = uuid4()
    collection = SimpleNamespace(
        id=collection_id,
        project_id=project_id,
        name="Knowledge",
        description=None,
        status=CollectionStatus.ACTIVE,
        created_at=None,
        updated_at=None,
    )
    collection_repo = AsyncMock()
    collection_repo.get_by_id.return_value = collection
    collection_repo.update.side_effect = lambda item: item
    agent_collection_repo = AsyncMock()
    agent_collection_repo.list_by_collection.return_value = []
    use_case = UpdateCollectionUseCase(
        collection_repo,
        agent_collection_repo,
    )

    result = await use_case.execute(
        UpdateCollectionInput(
            collection_id=collection_id,
            status=CollectionStatus.DELETED,
        )
    )

    assert result.status == CollectionStatus.DELETED
    assert collection.status == CollectionStatus.DELETED
    collection_repo.update.assert_awaited_once()
