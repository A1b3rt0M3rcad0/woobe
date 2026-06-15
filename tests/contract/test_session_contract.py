"""Contract tests for spec 002 — stateful/stateless session contract.

Defines the normative behaviour for session lifecycle. Tests are expected
to fail (red) against current production code and pass after specs 003-007.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.handlers.session_resolver import SessionResolver
from modules.agent.domain.entities import Session
from modules.agent.domain.enums import (
    RuntimeSessionMode,
    SessionStatus,
)
from modules.agent.domain.errors import SessionNotFoundError
from modules.agent.domain.repositories import SessionRepository


@pytest.fixture
def mock_session_repo() -> AsyncMock:
    repo = AsyncMock(spec=SessionRepository)

    existing_session = Session(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        mode=RuntimeSessionMode.CHAT,
        status=SessionStatus.ACTIVE,
    )

    async def _get_by_id(session_id):
        if session_id == existing_session.id:
            return existing_session
        raise SessionNotFoundError(session_id)

    repo.get_by_id = AsyncMock(side_effect=_get_by_id)
    repo.create = AsyncMock(side_effect=lambda s: s)
    return repo, existing_session


@pytest.fixture
def resolver(mock_session_repo: tuple[AsyncMock, Session]) -> SessionResolver:
    repo, _ = mock_session_repo
    return SessionResolver(repo)


# ── Stateful without session_id ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_stateful_without_session_id_creates_new_session(
    resolver: SessionResolver,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateful without session_id must create exactly one new session."""
    repo, _ = mock_session_repo
    session = await resolver.resolve(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=None,
        tenant_id=None,
        user_id=None,
        session_mode="stateful",
    )
    assert session is not None
    assert repo.create.call_count == 1


# ── Stateful with valid session_id ───────────────────────────────────────


@pytest.mark.asyncio
async def test_stateful_with_valid_session_reuses_exactly(
    resolver: SessionResolver,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateful with a known session_id must return that session, not a new one."""
    repo, existing = mock_session_repo
    session = await resolver.resolve(
        project_id=existing.project_id,
        agent_id=existing.agent_id,
        session_id=existing.id,
        tenant_id=None,
        user_id=None,
        session_mode="stateful",
    )
    assert session is not None
    assert session.id == existing.id
    assert repo.create.call_count == 0


# ── Stateful with invalid session_id ─────────────────────────────────────


@pytest.mark.asyncio
async def test_stateful_with_invalid_session_id_raises_error(
    resolver: SessionResolver,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateful with an unknown session_id must NOT create a new session."""
    repo, _ = mock_session_repo
    with pytest.raises(SessionNotFoundError):
        await resolver.resolve(
            project_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert repo.create.call_count == 0, (
        "Session created despite invalid session_id — contract violation"
    )


# ── Stateless contract ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stateless_does_not_create_session(
    resolver: SessionResolver,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateless mode must NOT create or return a session."""
    repo, _ = mock_session_repo
    session = await resolver.resolve(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        tenant_id=None,
        user_id=None,
        session_mode="stateless",
    )
    assert session is None
    assert repo.create.call_count == 0


@pytest.mark.asyncio
async def test_stateless_does_not_persist_messages() -> None:
    """Stateless mode must NOT persist user or assistant messages.

    Stateless means no session, so no messages can be persisted.
    This is enforced by the resolver returning None.
    """
    repo = AsyncMock(spec=SessionRepository)
    resolver = SessionResolver(repo)
    session = await resolver.resolve(
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=None,
        tenant_id=None,
        user_id=None,
        session_mode="stateless",
    )
    assert session is None


# ── Session status does not control memory ───────────────────────────────


def test_session_status_active_is_not_a_memory_signal() -> None:
    """Session status 'active' authorises execution, not memory.

    Memory is controlled by session_mode (stateful/stateless), not status.
    """
    session = Session(
        id=uuid4(),
        status=SessionStatus.ACTIVE,
        mode=RuntimeSessionMode.CHAT,
    )
    assert session.status == SessionStatus.ACTIVE
    assert session.mode == RuntimeSessionMode.CHAT
    session.status = SessionStatus.CLOSED
    assert session.mode == RuntimeSessionMode.CHAT
