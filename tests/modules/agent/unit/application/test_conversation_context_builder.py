"""Unit tests for ConversationContextBuilder — spec 007.

Tests cover:
- same session returned as resolved
- same history counters
- same errors for invalid session
- history limit configuration
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.handlers.conversation_context_builder import (
    ConversationContextBuilder,
)
from modules.agent.domain.entities import Message, Session
from modules.agent.domain.enums import (
    MessageRole,
    RuntimeSessionMode,
    SessionMode,
    SessionStatus,
)
from modules.agent.domain.errors import SessionNotFoundError
from modules.agent.domain.repositories import (
    MessageRepository,
    SessionRepository,
)


@pytest.fixture
def existing_session() -> Session:
    return Session(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        tenant_id="t1",
        user_id="u1",
        mode=RuntimeSessionMode.CHAT,
        status=SessionStatus.ACTIVE,
    )


@pytest.fixture
def mock_repos(existing_session: Session) -> tuple[AsyncMock, AsyncMock]:
    session_repo = AsyncMock(spec=SessionRepository)

    async def _get_by_id(sid):
        if sid == existing_session.id:
            return existing_session
        raise SessionNotFoundError(sid)

    session_repo.get_by_id = AsyncMock(side_effect=_get_by_id)
    session_repo.create = AsyncMock(side_effect=lambda s: s)
    session_repo.update = AsyncMock()

    message_repo = AsyncMock(spec=MessageRepository)
    message_repo.list_recent_by_session = AsyncMock(return_value=[])
    message_repo.create = AsyncMock(side_effect=lambda m: m)

    return session_repo, message_repo


@pytest.fixture
def mock_agent() -> AsyncMock:
    agent = AsyncMock()
    agent.session_mode = SessionMode.stateful
    agent.id = uuid4()
    agent.system_prompt = "You are helpful."
    agent.settings = None
    return agent


# ── Same session returned ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_builder_returns_existing_session(
    mock_repos: tuple[AsyncMock, AsyncMock],
    existing_session: Session,
    mock_agent: AsyncMock,
) -> None:
    """Builder must return the resolved session (existing)."""
    session_repo, message_repo = mock_repos
    builder = ConversationContextBuilder(session_repo, message_repo)
    input_dto = AskInput(
        project_id=existing_session.project_id,
        agent_id=existing_session.agent_id,
        message="hello",
        session_id=existing_session.id,
        tenant_id="t1",
        user_id="u1",
    )
    ctx = await builder.build(input_dto=input_dto, agent=mock_agent)
    assert ctx.session is not None
    assert ctx.session.id == existing_session.id


@pytest.mark.asyncio
async def test_builder_creates_new_session_when_no_id(
    mock_repos: tuple[AsyncMock, AsyncMock],
    mock_agent: AsyncMock,
) -> None:
    """Builder must create a new session when stateful and no session_id."""
    session_repo, message_repo = mock_repos
    builder = ConversationContextBuilder(session_repo, message_repo)
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="hello",
        session_id=None,
    )
    ctx = await builder.build(input_dto=input_dto, agent=mock_agent)
    assert ctx.session is not None
    assert session_repo.create.call_count == 1


# ── History counters ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_counters(
    mock_repos: tuple[AsyncMock, AsyncMock],
    existing_session: Session,
    mock_agent: AsyncMock,
) -> None:
    """Builder must report history_message_count and history_truncated."""
    session_repo, message_repo = mock_repos
    message_repo.list_recent_by_session.return_value = [
        Message(id=uuid4(), session_id=existing_session.id, role=MessageRole.USER, content="prev"),
    ]
    builder = ConversationContextBuilder(session_repo, message_repo)
    input_dto = AskInput(
        project_id=existing_session.project_id,
        agent_id=existing_session.agent_id,
        message="hello",
        session_id=existing_session.id,
        tenant_id="t1",
        user_id="u1",
    )
    ctx = await builder.build(input_dto=input_dto, agent=mock_agent)
    assert ctx.history_message_count == 1
    assert ctx.history_truncated  # 1 message loaded, default limit=100


# ── Same errors for invalid session ──────────────────────────────────────


@pytest.mark.asyncio
async def test_builder_propagates_session_not_found(
    mock_repos: tuple[AsyncMock, AsyncMock],
    mock_agent: AsyncMock,
) -> None:
    """Builder must propagate SessionNotFoundError for unknown session_id."""
    session_repo, message_repo = mock_repos
    builder = ConversationContextBuilder(session_repo, message_repo)
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="hello",
        session_id=uuid4(),
    )
    with pytest.raises(SessionNotFoundError):
        await builder.build(input_dto=input_dto, agent=mock_agent)
    assert session_repo.create.call_count == 0


@pytest.mark.asyncio
async def test_builder_stateless_returns_none(
    mock_repos: tuple[AsyncMock, AsyncMock],
    mock_agent: AsyncMock,
) -> None:
    """Stateless mode must return session=None and not persist."""
    session_repo, message_repo = mock_repos
    builder = ConversationContextBuilder(session_repo, message_repo)
    mock_agent.session_mode = SessionMode.stateless
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="stateless test",
        session_id=None,
    )
    ctx = await builder.build(input_dto=input_dto, agent=mock_agent)
    assert ctx.session is None
    assert ctx.user_message_id is None
    assert session_repo.create.call_count == 0
    assert message_repo.create.call_count == 0


# ── History limit configuration ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_builder_uses_history_limit(
    mock_repos: tuple[AsyncMock, AsyncMock],
    existing_session: Session,
    mock_agent: AsyncMock,
) -> None:
    """Builder must pass the history limit from agent settings."""
    session_repo, message_repo = mock_repos
    mock_agent.settings = {"history_max_messages": 10}
    builder = ConversationContextBuilder(session_repo, message_repo)
    input_dto = AskInput(
        project_id=existing_session.project_id,
        agent_id=existing_session.agent_id,
        message="hello",
        session_id=existing_session.id,
        tenant_id="t1",
        user_id="u1",
    )
    await builder.build(input_dto=input_dto, agent=mock_agent)
    assert message_repo.list_recent_by_session.call_count == 1
    call_kwargs = message_repo.list_recent_by_session.call_args
    assert call_kwargs is not None
    _, kwargs = call_kwargs
    assert kwargs.get("limit") == 10
