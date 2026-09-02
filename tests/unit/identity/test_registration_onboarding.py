from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.identity.application.auth_types import IssuedSession
from modules.identity.application.instance_types import InstanceState
from modules.identity.application.use_cases.authentication_use_cases import (
    DEFAULT_WORKSPACE_NAME,
    CreateOwnedWorkspaceUseCase,
    RegisterAuthenticationUseCase,
)
from modules.identity.domain.enums import MemberRole, WorkspaceStatus, UserStatus


def _token_issuer():
    return SimpleNamespace(
        ttl_seconds=900,
        issue=lambda **_: "access-token",
    )


@pytest.mark.asyncio
async def test_register_provisions_default_owned_workspace_and_returns_it() -> None:
    session_id = uuid4()
    owner_id = uuid4()
    instance_repo = AsyncMock()
    instance_repo.get_state.return_value = InstanceState(
        owner_user_id=owner_id,
        initialized_at=datetime.now(UTC),
        signup_mode="open",
        telemetry_enabled=False,
        user_count=1,
    )

    user_repo = AsyncMock()
    user_repo.get_by_email.return_value = None
    user_repo.save.side_effect = lambda entity: entity
    workspace_repo = AsyncMock()
    workspace_repo.get_by_slug.return_value = None
    workspace_repo.save.side_effect = lambda entity: entity
    member_repo = AsyncMock()
    member_repo.save.side_effect = lambda entity: entity
    outbox = AsyncMock()
    session_repo = AsyncMock()

    issued_user_id = None

    async def issue(*, user_id, user_agent, ip_address):
        nonlocal issued_user_id
        issued_user_id = user_id
        return IssuedSession(id=session_id, user_id=user_id, secret="refresh-secret")

    session_repo.issue.side_effect = issue
    use_case = RegisterAuthenticationUseCase(
        instance_repo,
        user_repo,
        workspace_repo,
        member_repo,
        outbox,
        session_repo,
        _token_issuer(),
    )

    result = await use_case.execute(
        email=" Owner@Example.com ",
        password="password",
        user_agent="pytest",
        ip_address="127.0.0.1",
    )

    assert result.user.email == "owner@example.com"
    assert result.user.status == UserStatus.active.value
    assert result.workspace is not None
    assert result.workspace.name == DEFAULT_WORKSPACE_NAME
    assert result.workspace.slug == f"workspace-{str(result.user.id)[:8]}"
    assert issued_user_id == result.user.id

    saved_workspace = workspace_repo.save.await_args.args[0]
    assert saved_workspace.name == DEFAULT_WORKSPACE_NAME
    assert saved_workspace.slug == f"workspace-{str(result.user.id)[:8]}"
    assert saved_workspace.status == WorkspaceStatus.active

    saved_member = member_repo.save.await_args.args[0]
    assert saved_member.user_id == result.user.id
    assert saved_member.workspace_id == saved_workspace.id
    assert saved_member.role == MemberRole.owner

    event_types = [call.kwargs["event_type"] for call in outbox.write.await_args_list]
    assert event_types == [
        "user.created.v1",
        "workspace.created.v1",
        "workspace.member_added.v1",
    ]


@pytest.mark.asyncio
async def test_create_workspace_adds_authenticated_user_as_owner() -> None:
    user_id = uuid4()
    user_repo = AsyncMock()
    user_repo.get_by_id.return_value = SimpleNamespace(
        id=user_id,
        status=UserStatus.active,
    )
    workspace_repo = AsyncMock()
    workspace_repo.get_by_slug.return_value = None
    workspace_repo.save.side_effect = lambda entity: entity
    member_repo = AsyncMock()
    member_repo.save.side_effect = lambda entity: entity
    outbox = AsyncMock()

    use_case = CreateOwnedWorkspaceUseCase(
        user_repo,
        workspace_repo,
        member_repo,
        outbox,
    )
    result = await use_case.execute(
        user_id=user_id,
        name=" Second Workspace ",
        slug="SECOND-WORKSPACE",
    )

    assert result.name == "Second Workspace"
    assert result.slug == "second-workspace"
    saved_member = member_repo.save.await_args.args[0]
    assert saved_member.user_id == user_id
    assert saved_member.workspace_id == result.id
    assert saved_member.role == MemberRole.owner

    event_types = [call.kwargs["event_type"] for call in outbox.write.await_args_list]
    assert event_types == [
        "workspace.created.v1",
        "workspace.member_added.v1",
    ]
