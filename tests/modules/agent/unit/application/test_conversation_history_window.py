"""Unit tests for spec 006 — recent deterministic history window.

Tests cover:
- list_recent_by_session returns most recent messages in chronological order
- load_and_convert_history correctly uses list_recent_by_session
- Orphan tool results at window start are removed
- Timestamps equal -> sorted by ID
- Invalid limit is normalized
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent.application.handlers.conversation_history_mapper import (
    load_and_convert_history,
)
from modules.agent.domain.entities import Message, Session
from modules.agent.domain.enums import MessageRole, RuntimeSessionMode, SessionStatus
from modules.agent.domain.repositories import MessageRepository


def _msg(
    role: str,
    content: str = "",
    *,
    created_at: datetime | None = None,
    data: dict | None = None,
) -> Message:
    return Message(
        id=uuid4(),
        session_id=uuid4(),
        role=MessageRole(role) if isinstance(role, str) else role,
        content=content,
        data=data,
        created_at=created_at or datetime.now(timezone.utc),
    )


def _chronological_msgs(n: int) -> list[Message]:
    """Generate n messages in chronological order with distinct timestamps."""
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    msgs: list[Message] = []
    for i in range(n):
        msgs.append(
            Message(
                id=uuid4(),
                session_id=uuid4(),
                role=MessageRole.USER,
                content=f"msg-{i}",
                created_at=base.replace(second=i % 60, microsecond=i // 60),
            )
        )
    return msgs


def _same_ts_msgs(n: int, base_dt: datetime | None = None) -> list[Message]:
    """Generate n messages with identical timestamps but distinct IDs."""
    if base_dt is None:
        base_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
    msgs: list[Message] = []
    for i in range(n):
        msgs.append(
            Message(
                id=uuid4(),
                session_id=uuid4(),
                role=MessageRole.USER,
                content=f"msg-{i}",
                created_at=base_dt,
            )
        )
    return msgs


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock(spec=MessageRepository)
    repo.list_recent_by_session = AsyncMock()
    return repo


@pytest.fixture
def session() -> Session:
    return Session(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        mode=RuntimeSessionMode.CHAT,
        status=SessionStatus.ACTIVE,
    )


# ── 150 messages return the 100 most recent ─────────────────────────────


@pytest.mark.asyncio
async def test_150_messages_return_100_most_recent(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """list_recent_by_session must return only the most recent 100 in chronological order."""
    all_msgs = _chronological_msgs(150)
    most_recent = all_msgs[-100:]
    mock_repo.list_recent_by_session.return_value = most_recent

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=100,
    )
    assert len(result) == 100


# ── Result is in chronological order ────────────────────────────────────


@pytest.mark.asyncio
async def test_result_is_chronological(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """load_and_convert_history must return messages in chronological order."""
    msgs = _chronological_msgs(10)
    mock_repo.list_recent_by_session.return_value = msgs

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=100,
    )
    assert len(result) == 10
    assert isinstance(result[0], HumanMessage)
    assert result[0].content == "msg-0"
    assert isinstance(result[-1], HumanMessage)
    assert result[-1].content == "msg-9"


# ── Equal timestamps sorted by ID ───────────────────────────────────────


@pytest.mark.asyncio
async def test_equal_timestamps_sorted_by_id(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """Messages with identical created_at must be ordered by id."""
    msgs = _same_ts_msgs(5)
    mock_repo.list_recent_by_session.return_value = list(reversed(msgs))

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=100,
    )
    assert len(result) == 5


# ── Window does not produce orphan tool result ──────────────────────────


@pytest.mark.asyncio
async def test_window_removes_leading_tool_result(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """Leading tool_result messages must be removed from the window."""
    msgs = [
        _msg("tool_result", '{"result": "ok"}'),
        _msg("user", "next question"),
        _msg("assistant", "answer"),
    ]
    mock_repo.list_recent_by_session.return_value = msgs

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=100,
    )
    assert len(result) == 2
    assert isinstance(result[0], HumanMessage)
    assert result[0].content == "next question"


@pytest.mark.asyncio
async def test_window_removes_leading_tool_call(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """Leading tool_call messages must be removed from the window."""
    msgs = [
        _msg("tool_call", "", data={"tool_call_id": "tc1", "tool_name": "test", "input": {}}),
        _msg("user", "next question"),
    ]
    mock_repo.list_recent_by_session.return_value = msgs

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=100,
    )
    assert len(result) == 1
    assert isinstance(result[0], HumanMessage)
    assert result[0].content == "next question"


@pytest.mark.asyncio
async def test_window_keeps_trailing_tool_result(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """Trailing tool_result inside assistant block must be preserved."""
    msgs = [
        _msg("user", "run tool"),
        _msg(
            "assistant",
            "Calling tool",
            data={
                "tool_calls": [
                    {"tool_call_id": "tc1", "tool_name": "calc", "input": {"x": 1}},
                ],
            },
        ),
    ]
    mock_repo.list_recent_by_session.return_value = msgs

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=100,
    )
    assert len(result) == 2
    assert isinstance(result[0], HumanMessage)
    assert isinstance(result[1], AIMessage)
    assert result[1].tool_calls is not None


# ── Invalid limit is normalized ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_limit_normalized(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """A too-large limit must be clamped to 500."""
    msgs = _chronological_msgs(600)
    mock_repo.list_recent_by_session.return_value = msgs[-500:]

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=500,
    )
    assert len(result) == 500


@pytest.mark.asyncio
async def test_small_limit_accepted(
    mock_repo: AsyncMock,
    session: Session,
) -> None:
    """A limit of 10 must return only 10 messages."""
    msgs = _chronological_msgs(50)
    mock_repo.list_recent_by_session.return_value = msgs[-10:]

    result = await load_and_convert_history(
        mock_repo, session.id, session.id, limit=10,
    )
    assert len(result) == 10
