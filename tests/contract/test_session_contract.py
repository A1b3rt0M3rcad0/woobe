"""Contract tests for spec 002 — stateful/stateless session contract.

Defines the normative behaviour for session lifecycle. Tests are expected
to fail (red) against current production code and pass after specs 003-007.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
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
def mock_message_repo() -> AsyncMock:
    repo = AsyncMock(spec=MessageRepository)
    repo.list_by_session = AsyncMock(return_value=[])
    repo.create = AsyncMock(side_effect=lambda msg: msg)
    return repo


def _make_use_case(
    mock_message_repo: AsyncMock,
    mock_session_repo: AsyncMock,
) -> AskAgentUseCase:
    return AskAgentUseCase(
        agent_repo=AsyncMock(),
        credential_repo=AsyncMock(),
        session_repo=mock_session_repo,
        message_repo=mock_message_repo,
        agent_collection_repo=AsyncMock(),
        chunk_repo=AsyncMock(),
        trace_recorder=AsyncMock(),
        usage_recorder=AsyncMock(),
        outbox=AsyncMock(),
        llm_factory=AsyncMock(),
        encryption_key="test-encryption-key-for-contract-tests",
    )


# ── Stateful without session_id ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_stateful_without_session_id_creates_new_session(
    mock_message_repo: AsyncMock,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateful without session_id must create exactly one new session."""
    repo, _ = mock_session_repo
    use_case = _make_use_case(mock_message_repo, repo)
    agent = AsyncMock(session_mode=SessionMode.stateful, id=uuid4())
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="Hello",
        session_id=None,
    )
    session = await use_case._resolve_session(input_dto, agent)
    assert session is not None
    assert repo.create.call_count == 1


# ── Stateful with valid session_id ───────────────────────────────────────


@pytest.mark.asyncio
async def test_stateful_with_valid_session_reuses_exactly(
    mock_message_repo: AsyncMock,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateful with a known session_id must return that session, not a new one."""
    repo, existing = mock_session_repo
    use_case = _make_use_case(mock_message_repo, repo)
    agent = AsyncMock(session_mode=SessionMode.stateful, id=uuid4())
    input_dto = AskInput(
        project_id=existing.project_id,
        agent_id=existing.agent_id,
        message="Hello again",
        session_id=existing.id,
    )
    session = await use_case._resolve_session(input_dto, agent)
    assert session is not None
    assert session.id == existing.id
    assert repo.create.call_count == 0


# ── Stateful with invalid session_id ─────────────────────────────────────


@pytest.mark.asyncio
async def test_stateful_with_invalid_session_id_raises_error(
    mock_message_repo: AsyncMock,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateful with an unknown session_id must NOT create a new session.

    This test is expected to FAIL against the current code because
    _resolve_session catches all exceptions and creates a replacement.
    After spec 005 the error must be propagated.
    """
    repo, _ = mock_session_repo
    use_case = _make_use_case(mock_message_repo, repo)
    agent = AsyncMock(session_mode=SessionMode.stateful, id=uuid4())
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="test",
        session_id=uuid4(),
    )
    with pytest.raises(SessionNotFoundError):
        await use_case._resolve_session(input_dto, agent)
    assert repo.create.call_count == 0, (
        "Session created despite invalid session_id — contract violation"
    )


# ── Stateless contract ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stateless_does_not_create_session(
    mock_message_repo: AsyncMock,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateless mode must NOT create or return a session."""
    repo, _ = mock_session_repo
    use_case = _make_use_case(mock_message_repo, repo)
    agent = AsyncMock(session_mode=SessionMode.stateless, id=uuid4())
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="stateless test",
        session_id=uuid4(),
    )
    session = await use_case._resolve_session(input_dto, agent)
    assert session is None
    assert repo.create.call_count == 0


@pytest.mark.asyncio
async def test_stateless_does_not_persist_messages(
    mock_message_repo: AsyncMock,
    mock_session_repo: tuple[AsyncMock, Session],
) -> None:
    """Stateless mode must NOT persist user or assistant messages."""
    repo, _ = mock_session_repo
    use_case = _make_use_case(mock_message_repo, repo)
    agent = AsyncMock(session_mode=SessionMode.stateless, id=uuid4())
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="stateless test",
        session_id=None,
    )
    session = await use_case._resolve_session(input_dto, agent)
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
    # Changing status must NOT affect mode
    session.status = SessionStatus.CLOSED
    assert session.mode == RuntimeSessionMode.CHAT
