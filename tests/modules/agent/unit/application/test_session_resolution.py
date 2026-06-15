"""Unit tests for SessionResolver — spec 005.

Tests cover:
- nonexistent session_id does not create a session
- session from another agent is rejected
- session from another project is rejected
- tenant/user mismatch is rejected
- closed/expired/error sessions are rejected
- stateful without session_id creates exactly one session
- stateless creates zero sessions and does not query repo
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.handlers.session_resolver import SessionResolver
from modules.agent.domain.entities import Session
from modules.agent.domain.enums import RuntimeSessionMode, SessionStatus
from modules.agent.domain.errors import (
    SessionInvalidStatusError,
    SessionNotFoundError,
    SessionOwnershipMismatchError,
)
from modules.agent.domain.repositories import SessionRepository


@pytest.fixture
def valid_session() -> Session:
    return Session(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        tenant_id="tenant-1",
        user_id="user-1",
        mode=RuntimeSessionMode.CHAT,
        status=SessionStatus.ACTIVE,
    )


@pytest.fixture
def mock_repo(valid_session: Session) -> AsyncMock:
    repo = AsyncMock(spec=SessionRepository)

    async def _get_by_id(session_id):
        if session_id == valid_session.id:
            return valid_session
        raise SessionNotFoundError(session_id)

    repo.get_by_id = AsyncMock(side_effect=_get_by_id)
    repo.create = AsyncMock(side_effect=lambda s: s)
    return repo


@pytest.fixture
def resolver(mock_repo: AsyncMock) -> SessionResolver:
    return SessionResolver(mock_repo)


# ── 1. nonexistent session_id does not create a session ─────────────


@pytest.mark.asyncio
async def test_nonexistent_id_does_not_create_session(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
) -> None:
    """Stateful with an unknown session_id must NOT create a new session."""
    unknown_id = uuid4()
    with pytest.raises(SessionNotFoundError):
        await resolver.resolve(
            project_id=uuid4(),
            agent_id=uuid4(),
            session_id=unknown_id,
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


# ── 2. session from another agent is rejected ────────────────────────


@pytest.mark.asyncio
async def test_session_from_other_agent_is_not_accepted(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
    valid_session: Session,
) -> None:
    """Session belonging to a different agent_id must be rejected."""
    with pytest.raises(SessionOwnershipMismatchError):
        await resolver.resolve(
            project_id=valid_session.project_id,
            agent_id=uuid4(),  # different agent
            session_id=valid_session.id,
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


# ── 3. session from another project is rejected ──────────────────────


@pytest.mark.asyncio
async def test_session_from_other_project_is_not_accepted(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
    valid_session: Session,
) -> None:
    """Session belonging to a different project_id must be rejected."""
    with pytest.raises(SessionOwnershipMismatchError):
        await resolver.resolve(
            project_id=uuid4(),  # different project
            agent_id=valid_session.agent_id,
            session_id=valid_session.id,
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


# ── 4. tenant/user mismatch is rejected ──────────────────────────────


@pytest.mark.asyncio
async def test_tenant_mismatch_is_not_accepted(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
    valid_session: Session,
) -> None:
    """Tenant mismatch (both sides filled) must be rejected."""
    with pytest.raises(SessionOwnershipMismatchError):
        await resolver.resolve(
            project_id=valid_session.project_id,
            agent_id=valid_session.agent_id,
            session_id=valid_session.id,
            tenant_id="different-tenant",
            user_id=valid_session.user_id,
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


@pytest.mark.asyncio
async def test_user_mismatch_is_not_accepted(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
    valid_session: Session,
) -> None:
    """User mismatch (both sides filled) must be rejected."""
    with pytest.raises(SessionOwnershipMismatchError):
        await resolver.resolve(
            project_id=valid_session.project_id,
            agent_id=valid_session.agent_id,
            session_id=valid_session.id,
            tenant_id=valid_session.tenant_id,
            user_id="different-user",
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


@pytest.mark.asyncio
async def test_tenant_mismatch_with_input_tenant_none_is_allowed(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
    valid_session: Session,
) -> None:
    """When input tenant_id is None, session tenant_id is NOT checked."""
    session = await resolver.resolve(
        project_id=valid_session.project_id,
        agent_id=valid_session.agent_id,
        session_id=valid_session.id,
        tenant_id=None,  # not provided in this request
        user_id=None,  # not provided
        session_mode="stateful",
    )
    assert session is not None
    assert session.id == valid_session.id


# ── 5. closed/expired/error sessions are rejected ────────────────────


@pytest.mark.asyncio
async def test_closed_session_does_not_receive_new_messages(
    valid_session: Session,
    mock_repo: AsyncMock,
    resolver: SessionResolver,
) -> None:
    """A closed session must be rejected."""
    valid_session.status = SessionStatus.CLOSED
    with pytest.raises(SessionInvalidStatusError):
        await resolver.resolve(
            project_id=valid_session.project_id,
            agent_id=valid_session.agent_id,
            session_id=valid_session.id,
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


@pytest.mark.asyncio
async def test_expired_session_does_not_receive_new_messages(
    valid_session: Session,
    mock_repo: AsyncMock,
    resolver: SessionResolver,
) -> None:
    """An expired session must be rejected."""
    valid_session.status = SessionStatus.EXPIRED
    with pytest.raises(SessionInvalidStatusError):
        await resolver.resolve(
            project_id=valid_session.project_id,
            agent_id=valid_session.agent_id,
            session_id=valid_session.id,
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


@pytest.mark.asyncio
async def test_error_session_does_not_receive_new_messages(
    valid_session: Session,
    mock_repo: AsyncMock,
    resolver: SessionResolver,
) -> None:
    """A session in error status must be rejected."""
    valid_session.status = SessionStatus.ERROR
    with pytest.raises(SessionInvalidStatusError):
        await resolver.resolve(
            project_id=valid_session.project_id,
            agent_id=valid_session.agent_id,
            session_id=valid_session.id,
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert mock_repo.create.call_count == 0


# ── 6. stateful without session_id creates exactly one session ───────


@pytest.mark.asyncio
async def test_stateful_without_id_creates_exactly_one_session(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
) -> None:
    """Stateful mode without a session_id must create exactly one session."""
    project_id = uuid4()
    agent_id = uuid4()

    session = await resolver.resolve(
        project_id=project_id,
        agent_id=agent_id,
        session_id=None,
        tenant_id=None,
        user_id=None,
        session_mode="stateful",
    )
    assert session is not None
    assert session.project_id == project_id
    assert session.agent_id == agent_id
    assert mock_repo.create.call_count == 1


# ── 7. stateless creates zero sessions ────────────────────────────────


@pytest.mark.asyncio
async def test_stateless_creates_zero_sessions(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
) -> None:
    """Stateless mode must NOT create or query a session."""
    session = await resolver.resolve(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=None,
        tenant_id=None,
        user_id=None,
        session_mode="stateless",
    )
    assert session is None
    assert mock_repo.create.call_count == 0
    assert mock_repo.get_by_id.call_count == 0


@pytest.mark.asyncio
async def test_stateless_ignores_provided_session_id(
    resolver: SessionResolver,
    mock_repo: AsyncMock,
) -> None:
    """Stateless mode with a session_id must NOT query or create."""
    session = await resolver.resolve(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        tenant_id=None,
        user_id=None,
        session_mode="stateless",
    )
    assert session is None
    assert mock_repo.create.call_count == 0
    assert mock_repo.get_by_id.call_count == 0
