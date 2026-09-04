from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.identity.infra.services.authentication_service import (
    DEFAULT_WORKSPACE_NAME,
    AuthenticationService,
)
from modules.identity.infra.services.session_lifecycle import IssuedSession
from modules.identity.domain.enums import MemberRole, WorkspaceStatus, UserStatus


class FakeIdentityUnitOfWork:
    current = None

    def __init__(self, _session_factory) -> None:
        self.uow = self.current

    async def __aenter__(self):
        return self.uow

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def make_service() -> AuthenticationService:
    token_codec = SimpleNamespace(
        ttl_seconds=900,
        issue=lambda **_: "access-token",
    )
    settings = SimpleNamespace(refresh_token_ttl_days=30)
    return AuthenticationService(SimpleNamespace(), token_codec, settings)


def patch_repositories(monkeypatch) -> None:
    module = "modules.identity.infra.services.authentication_service"
    bindings = {
        "SQLAlchemyUserRepository": "users",
        "SQLAlchemyWorkspaceRepository": "workspaces",
        "SQLAlchemyWorkspaceMemberRepository": "members",
        "SQLAlchemyOutboxEventWriter": "outbox",
    }
    for repository_name, attribute_name in bindings.items():
        monkeypatch.setattr(
            f"{module}.{repository_name}",
            lambda uow, attribute_name=attribute_name: getattr(uow, attribute_name),
        )


@pytest.mark.asyncio
async def test_register_provisions_default_owned_workspace_and_returns_it(monkeypatch) -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    member_id = uuid4()
    session_id = uuid4()

    user = SimpleNamespace(
        id=user_id,
        email="owner@example.com",
        password="hashed",
        status=UserStatus.active,
    )
    workspace = SimpleNamespace(
        id=workspace_id,
        name=DEFAULT_WORKSPACE_NAME,
        slug=f"workspace-{str(user_id)[:8]}",
        status=WorkspaceStatus.active,
    )
    member = SimpleNamespace(
        id=member_id,
        user_id=user_id,
        workspace_id=workspace_id,
        role=MemberRole.owner,
    )

    uow = SimpleNamespace(
        users=SimpleNamespace(
            get_by_email=AsyncMock(return_value=None),
            save=AsyncMock(return_value=user),
        ),
        workspaces=SimpleNamespace(
            get_by_slug=AsyncMock(return_value=None),
            save=AsyncMock(return_value=workspace),
        ),
        members=SimpleNamespace(save=AsyncMock(return_value=member)),
        outbox=SimpleNamespace(write=AsyncMock()),
    )
    FakeIdentityUnitOfWork.current = uow
    monkeypatch.setattr(
        "modules.identity.infra.services.authentication_service.IdentityUnitOfWork",
        FakeIdentityUnitOfWork,
    )
    patch_repositories(monkeypatch)

    service = make_service()
    service._sessions.issue = AsyncMock(
        return_value=IssuedSession(
            id=session_id,
            user_id=user_id,
            secret="refresh-secret",
        )
    )

    result = await service.register(
        email=" Owner@Example.com ",
        password="password",
        user_agent="pytest",
        ip_address="127.0.0.1",
    )

    assert result.user.id == user_id
    assert result.workspace is not None
    assert result.workspace.id == workspace_id
    assert result.workspace.name == DEFAULT_WORKSPACE_NAME
    assert result.workspace.slug == f"workspace-{str(user_id)[:8]}"

    saved_workspace = uow.workspaces.save.await_args.args[0]
    assert saved_workspace.name == DEFAULT_WORKSPACE_NAME
    assert saved_workspace.slug == f"workspace-{str(user_id)[:8]}"

    saved_member = uow.members.save.await_args.args[0]
    assert saved_member.user_id == user_id
    assert saved_member.workspace_id == workspace_id
    assert saved_member.role == MemberRole.owner

    event_types = [
        call.kwargs["event_type"]
        for call in uow.outbox.write.await_args_list
    ]
    assert event_types == [
        "user.created.v1",
        "workspace.created.v1",
        "workspace.member_added.v1",
    ]


@pytest.mark.asyncio
async def test_create_workspace_adds_authenticated_user_as_owner(monkeypatch) -> None:
    user_id = uuid4()
    workspace_id = uuid4()
    member_id = uuid4()

    user = SimpleNamespace(id=user_id, status=UserStatus.active)
    workspace = SimpleNamespace(
        id=workspace_id,
        name="Second Workspace",
        slug="second-workspace",
        status=WorkspaceStatus.active,
    )
    member = SimpleNamespace(
        id=member_id,
        user_id=user_id,
        workspace_id=workspace_id,
        role=MemberRole.owner,
    )
    uow = SimpleNamespace(
        users=SimpleNamespace(get_by_id=AsyncMock(return_value=user)),
        workspaces=SimpleNamespace(
            get_by_slug=AsyncMock(return_value=None),
            save=AsyncMock(return_value=workspace),
        ),
        members=SimpleNamespace(save=AsyncMock(return_value=member)),
        outbox=SimpleNamespace(write=AsyncMock()),
    )
    FakeIdentityUnitOfWork.current = uow
    monkeypatch.setattr(
        "modules.identity.infra.services.authentication_service.IdentityUnitOfWork",
        FakeIdentityUnitOfWork,
    )
    patch_repositories(monkeypatch)

    result = await make_service().create_workspace(
        user_id=user_id,
        name=" Second Workspace ",
        slug="SECOND-WORKSPACE",
    )

    assert result.id == workspace_id
    saved_member = uow.members.save.await_args.args[0]
    assert saved_member.user_id == user_id
    assert saved_member.workspace_id == workspace_id
    assert saved_member.role == MemberRole.owner

    event_types = [
        call.kwargs["event_type"]
        for call in uow.outbox.write.await_args_list
    ]
    assert event_types == [
        "workspace.created.v1",
        "workspace.member_added.v1",
    ]
