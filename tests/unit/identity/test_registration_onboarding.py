from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.identity.application.authentication_service import (
    DEFAULT_ORGANIZATION_NAME,
    AuthenticationService,
)
from modules.identity.application.session_lifecycle import IssuedSession
from modules.identity.domain.enums import MemberRole, OrganizationStatus, UserStatus


class FakeIdentityUnitOfWork:
    current = None

    def __init__(self, _session_factory) -> None:
        self.uow = self.current

    async def __aenter__(self):
        return self.uow

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


@pytest.mark.asyncio
async def test_register_provisions_default_owned_organization_and_returns_it(monkeypatch) -> None:
    user_id = uuid4()
    organization_id = uuid4()
    member_id = uuid4()
    session_id = uuid4()

    user = SimpleNamespace(
        id=user_id,
        email="owner@example.com",
        password="hashed",
        status=UserStatus.active,
    )
    organization = SimpleNamespace(
        id=organization_id,
        name=DEFAULT_ORGANIZATION_NAME,
        slug=f"org-{str(user_id)[:8]}",
        status=OrganizationStatus.active,
    )
    member = SimpleNamespace(
        id=member_id,
        user_id=user_id,
        organization_id=organization_id,
        role=MemberRole.owner,
    )

    uow = SimpleNamespace(
        users=SimpleNamespace(
            get_by_email=AsyncMock(return_value=None),
            save=AsyncMock(return_value=user),
        ),
        organizations=SimpleNamespace(
            get_by_slug=AsyncMock(return_value=None),
            save=AsyncMock(return_value=organization),
        ),
        members=SimpleNamespace(save=AsyncMock(return_value=member)),
        outbox=SimpleNamespace(write=AsyncMock()),
    )
    FakeIdentityUnitOfWork.current = uow
    monkeypatch.setattr(
        "modules.identity.application.authentication_service.IdentityUnitOfWork",
        FakeIdentityUnitOfWork,
    )

    token_codec = SimpleNamespace(
        ttl_seconds=900,
        issue=lambda **_: "access-token",
    )
    settings = SimpleNamespace(refresh_token_ttl_days=30)
    service = AuthenticationService(SimpleNamespace(), token_codec, settings)
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
    assert result.organization is not None
    assert result.organization.id == organization_id
    assert result.organization.name == DEFAULT_ORGANIZATION_NAME
    assert result.organization.slug == f"org-{str(user_id)[:8]}"

    saved_organization = uow.organizations.save.await_args.args[0]
    assert saved_organization.name == DEFAULT_ORGANIZATION_NAME
    assert saved_organization.slug == f"org-{str(user_id)[:8]}"

    saved_member = uow.members.save.await_args.args[0]
    assert saved_member.user_id == user_id
    assert saved_member.organization_id == organization_id
    assert saved_member.role == MemberRole.owner

    event_types = [
        call.kwargs["event_type"]
        for call in uow.outbox.write.await_args_list
    ]
    assert event_types == [
        "user.created.v1",
        "organization.created.v1",
        "organization.member_added.v1",
    ]
