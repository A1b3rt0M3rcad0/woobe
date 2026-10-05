from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.core.application.dtos.api_key_lifecycle_dtos import RotateApiKeyInput
from modules.core.application.dtos.create_api_key_dtos import CreateApiKeyInput
from modules.core.application.use_cases.api_key_lifecycle_use_cases import (
    RotateApiKeyUseCase,
)
from modules.core.application.use_cases.create_api_key_use_case import (
    CreateApiKeyUseCase,
)
from modules.core.domain.entities import ApiKey
from modules.core.domain.enums import ApiKeyKind, ApiKeyStatus


@pytest.mark.asyncio
async def test_control_key_can_be_audited_as_project_key_creator() -> None:
    project_id = uuid4()
    actor_key_id = uuid4()
    project_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=project_id))
    )
    api_key_repo = SimpleNamespace(save=AsyncMock(side_effect=lambda item: item))
    outbox = SimpleNamespace(write=AsyncMock())
    policy = SimpleNamespace(validate=AsyncMock())
    use_case = CreateApiKeyUseCase(
        project_repo, api_key_repo, outbox, delegation_policy=policy
    )

    await use_case.execute(
        CreateApiKeyInput(
            project_id=project_id,
            name="Automation key",
            scopes=["traces:read"],
            created_by_control_key_id=actor_key_id,
        )
    )

    policy.validate.assert_awaited_once_with(
        actor_key_id=actor_key_id,
        project_id=project_id,
        scopes=["traces:read"],
        conditions={},
        expires_at=None,
    )
    saved = api_key_repo.save.await_args.args[0]
    assert saved.created_by_user_id is None
    assert saved.created_by_control_key_id == actor_key_id
    payload = outbox.write.await_args.kwargs["payload"]
    assert payload["created_by_control_key_id"] == str(actor_key_id)


@pytest.mark.asyncio
async def test_control_key_can_be_audited_as_rotation_actor() -> None:
    project_id = uuid4()
    actor_key_id = uuid4()
    current = ApiKey(
        project_id=project_id,
        name="Automation key",
        scopes=["traces:read"],
        kind=ApiKeyKind.project,
        status=ApiKeyStatus.active,
        created_by_user_id=uuid4(),
    )
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=current),
        update=AsyncMock(side_effect=lambda item: item),
        save=AsyncMock(side_effect=lambda item: item),
    )
    outbox = SimpleNamespace(write=AsyncMock())
    policy = SimpleNamespace(validate=AsyncMock())
    use_case = RotateApiKeyUseCase(repo, outbox, delegation_policy=policy)

    await use_case.execute(
        RotateApiKeyInput(
            project_id=project_id,
            api_key_id=current.id,
            rotated_by_control_key_id=actor_key_id,
        )
    )

    replacement = repo.save.await_args.args[0]
    assert replacement.created_by_user_id is None
    assert replacement.created_by_control_key_id == actor_key_id
    payload = outbox.write.await_args.kwargs["payload"]
    assert payload["rotated_by_control_key_id"] == str(actor_key_id)
