from types import SimpleNamespace
from datetime import UTC, datetime, timedelta
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
from shared.contracts.errors import AuthorizationError


@pytest.mark.asyncio
async def test_control_key_can_be_audited_as_project_key_creator() -> None:
    project_id = uuid4()
    actor_key_id = uuid4()
    project_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=project_id))
    )
    api_key_repo = SimpleNamespace(save=AsyncMock(side_effect=lambda item: item))
    outbox = SimpleNamespace(write=AsyncMock())
    policy = SimpleNamespace(validate=AsyncMock(return_value=None))
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
    policy = SimpleNamespace(validate=AsyncMock(return_value=None))
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


@pytest.mark.asyncio
async def test_issued_key_persists_the_issuing_control_authority_ceiling():
    ceiling = datetime.now(UTC) + timedelta(hours=2)
    project_id = uuid4()
    repo = SimpleNamespace(save=AsyncMock(side_effect=lambda item: item))
    use_case = CreateApiKeyUseCase(
        SimpleNamespace(
            get_by_id=AsyncMock(return_value=SimpleNamespace(id=project_id))
        ),
        repo,
        SimpleNamespace(write=AsyncMock()),
        delegation_policy=SimpleNamespace(validate=AsyncMock(return_value=ceiling)),
    )
    await use_case.execute(
        CreateApiKeyInput(
            project_id=project_id,
            name="Delegated",
            scopes=["traces:read"],
            created_by_control_key_id=uuid4(),
            expires_at=ceiling - timedelta(minutes=10),
        )
    )
    assert repo.save.await_args.args[0].delegation_expires_at == ceiling


@pytest.mark.asyncio
@pytest.mark.parametrize("machine", [False, True])
async def test_rotation_cannot_extend_persisted_delegation_ceiling(machine):
    ceiling = datetime.now(UTC) + timedelta(hours=2)
    current = ApiKey(
        project_id=uuid4(),
        name="Delegated",
        scopes=["traces:read"],
        expires_at=ceiling,
        delegation_expires_at=ceiling,
    )
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=current),
        update=AsyncMock(),
        save=AsyncMock(),
    )
    outbox = SimpleNamespace(write=AsyncMock())
    use_case = RotateApiKeyUseCase(
        repo,
        outbox,
        delegation_policy=SimpleNamespace(validate=AsyncMock(return_value=None)),
    )
    actor = {"rotated_by_control_key_id" if machine else "rotated_by_user_id": uuid4()}
    with pytest.raises(AuthorizationError, match="delegation ceiling"):
        await use_case.execute(
            RotateApiKeyInput(
                project_id=current.project_id,
                api_key_id=current.id,
                expires_at=ceiling + timedelta(seconds=1),
                **actor,
            )
        )
    repo.update.assert_not_awaited()
    repo.save.assert_not_awaited()
    outbox.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_human_rotation_preserves_delegation_ceiling_for_next_rotation():
    ceiling = datetime.now(UTC) + timedelta(hours=2)
    current = ApiKey(
        project_id=uuid4(),
        name="Delegated",
        scopes=["traces:read"],
        expires_at=ceiling - timedelta(minutes=10),
        delegation_expires_at=ceiling,
    )
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=current),
        update=AsyncMock(side_effect=lambda item: item),
        save=AsyncMock(side_effect=lambda item: item),
    )
    await RotateApiKeyUseCase(repo, SimpleNamespace(write=AsyncMock())).execute(
        RotateApiKeyInput(
            project_id=current.project_id,
            api_key_id=current.id,
            rotated_by_user_id=uuid4(),
            expires_at=ceiling,
        )
    )
    replacement = repo.save.await_args.args[0]
    assert replacement.delegation_expires_at == ceiling
    assert replacement.expires_at == ceiling
