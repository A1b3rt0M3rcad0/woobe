from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.core.infra.services.control_key_service import ControlKeyService
from shared.infra.errors import AuthorizationError
from shared.security.principal import ControlPlanePrincipal


def _principal(*, permissions: set[str] | None = None) -> ControlPlanePrincipal:
    return ControlPlanePrincipal(
        api_key_id=uuid4(),
        credential_id=uuid4(),
        workspace_id=uuid4(),
        key_prefix="woobe_control_test",
        permissions=frozenset(permissions or {"keys:update", "keys:rotate", "keys:revoke"}),
        authenticated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_control_key_cannot_mutate_own_credential_lineage() -> None:
    actor = _principal()
    service = ControlKeyService.__new__(ControlKeyService)

    with pytest.raises(AuthorizationError, match="own credential"):
        await service._assert_target_manageable(
            object(),
            actor=actor,
            workspace_id=actor.workspace_id,
            target={
                "credential_id": actor.credential_id,
                "permissions": [],
            },
            target_grants=[],
        )


@pytest.mark.asyncio
async def test_control_key_cannot_manage_key_with_broader_workspace_permissions() -> None:
    actor = _principal(permissions={"keys:update"})
    service = ControlKeyService.__new__(ControlKeyService)

    with pytest.raises(AuthorizationError, match="broader Workspace permissions"):
        await service._assert_target_manageable(
            object(),
            actor=actor,
            workspace_id=actor.workspace_id,
            target={
                "credential_id": uuid4(),
                "permissions": ["keys:update", "keys:rotate"],
            },
            target_grants=[],
        )


@pytest.mark.asyncio
async def test_control_key_cannot_manage_key_with_broader_project_grant() -> None:
    actor = _principal()
    project_id = uuid4()
    service = ControlKeyService.__new__(ControlKeyService)
    service._grants_for_key = AsyncMock(
        return_value=[
            {
                "project_id": project_id,
                "permissions": ["agent:read"],
            }
        ]
    )

    with pytest.raises(AuthorizationError, match="broader Project access"):
        await service._assert_target_manageable(
            object(),
            actor=actor,
            workspace_id=actor.workspace_id,
            target={
                "credential_id": uuid4(),
                "permissions": [],
            },
            target_grants=[
                {
                    "project_id": project_id,
                    "permissions": ["agent:read", "agent:write"],
                }
            ],
        )


@pytest.mark.asyncio
async def test_multi_project_delegation_uses_one_authority_snapshot():
    actor = _principal()
    projects = [uuid4(), uuid4()]
    grants = [{"project_id": project, "permissions": ["agent:read"],
               "conditions": {"environments": ["staging"]}} for project in projects]
    service = ControlKeyService.__new__(ControlKeyService)
    service._grants_for_key = AsyncMock(side_effect=[grants, []])
    await service._validate_delegation(object(), actor=actor,
        workspace_id=actor.workspace_id, workspace_permissions=[], grants=grants)
    service._grants_for_key.assert_awaited_once()


@pytest.mark.asyncio
async def test_key_management_uses_one_consistent_grant_snapshot():
    actor = _principal()
    grant = {"project_id": uuid4(), "permissions": ["agent:read"],
             "conditions": {"environments": ["staging"]}}
    service = ControlKeyService.__new__(ControlKeyService)
    service._grants_for_key = AsyncMock(side_effect=[[grant], []])
    await service._assert_target_manageable(object(), actor=actor,
        workspace_id=actor.workspace_id,
        target={"credential_id": uuid4(), "permissions": []}, target_grants=[grant])
    service._grants_for_key.assert_awaited_once()
    unrestricted = {**grant, "conditions": {}}
    service._grants_for_key = AsyncMock(return_value=[grant])
    with pytest.raises(AuthorizationError, match="broader grant conditions"):
        await service._assert_target_manageable(object(), actor=actor,
            workspace_id=actor.workspace_id,
            target={"credential_id": uuid4(), "permissions": []}, target_grants=[unrestricted])
