"""Red tests reproducing session-history bugs.

These tests exercise production code directly and are expected to FAIL
before the corresponding fixes in specs 003-005. Each test targets one
specific defect:

- assistant without tool_calls erases history (except Exception: return [])
- current user turn appears twice in the prompt
- missing session_id silently creates a replacement session (FIXED in spec 005)
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent.application.handlers.conversation_context_builder import (
    ConversationContextBuilder,
)
from modules.agent.application.handlers.conversation_history_mapper import (
    load_and_convert_history,
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
def mock_session() -> Session:
    return Session(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        mode=RuntimeSessionMode.CHAT,
        status=SessionStatus.ACTIVE,
        tenant_id="tenant-1",
        user_id="user-1",
    )


@pytest.fixture
def mock_message_repo() -> AsyncMock:
    messages: dict[uuid4, list[Message]] = {}

    repo = AsyncMock(spec=MessageRepository)

    async def _create(msg: Message) -> Message:
        sid = msg.session_id
        if sid not in messages:
            messages[sid] = []
        messages[sid].append(msg)
        msg.id = uuid4()
        return msg

    async def _list_recent_by_session(session_id, limit=100):
        return messages.get(session_id, [
            Message(
                id=uuid4(),
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content="Entendido.",
                data=None,
            )
        ])

    async def _list_by_session(session_id, offset=0, limit=100):
        return messages.get(session_id, [
            Message(
                id=uuid4(),
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content="Entendido.",
                data=None,
            )
        ])

    repo.create = AsyncMock(side_effect=_create)
    repo.list_by_session = AsyncMock(side_effect=_list_by_session)
    repo.list_recent_by_session = AsyncMock(side_effect=_list_recent_by_session)
    return repo


@pytest.fixture
def mock_session_repo() -> AsyncMock:
    repo = AsyncMock(spec=SessionRepository)

    async def _get_by_id(session_id):
        raise SessionNotFoundError(session_id)

    repo.get_by_id = AsyncMock(side_effect=_get_by_id)
    repo.create = AsyncMock(side_effect=lambda s: s)
    repo.update = AsyncMock()
    return repo


# ── D1 + D2: assistant without tool_calls must not erase history ─────────


@pytest.mark.asyncio
async def test_assistant_without_tool_calls_must_not_erase_history(
    mock_message_repo: AsyncMock,
    mock_session: Session,
) -> None:
    """load_and_convert_history must not erase assistant messages that
    have no tool_calls (the AIMessage(tool_calls=None) bug)."""
    history = await load_and_convert_history(
        mock_message_repo, mock_session.id, mock_session.id, limit=100,
    )
    assert len(history) > 0, (
        "load_and_convert_history returned empty list for assistant message "
        "without tool_calls (the AIMessage(tool_calls=None) bug)"
    )
    assert isinstance(history[0], AIMessage)
    assert history[0].content == "Entendido."


# ── D3: current user turn must not appear twice ──────────────────────────


@pytest.mark.asyncio
async def test_current_user_turn_is_not_present_twice(
    mock_message_repo: AsyncMock,
    mock_session_repo: AsyncMock,
    mock_session: Session,
) -> None:
    """The full builder pipeline must produce the current turn exactly once."""
    builder = ConversationContextBuilder(mock_session_repo, mock_message_repo)

    agent = AsyncMock()
    agent.session_mode = SessionMode.stateful
    agent.id = mock_session.agent_id
    agent.system_prompt = "You are a helpful assistant."
    agent.settings = None

    from modules.agent.application.dtos.runtime_dtos import AskInput

    input_dto = AskInput(
        project_id=mock_session.project_id,
        agent_id=mock_session.agent_id,
        message="Qual é o meu código?",
        session_id=mock_session.id,
        tenant_id="tenant-1",
        user_id="user-1",
    )

    # Override session_repo.get_by_id to return our session
    async def _get_by_id(sid):
        return mock_session
    mock_session_repo.get_by_id = AsyncMock(side_effect=_get_by_id)

    ctx = await builder.build(input_dto=input_dto, agent=agent)

    human_messages = [m for m in ctx.prompt_messages if isinstance(m, HumanMessage)]
    assert len(human_messages) == 1, (
        f"Expected exactly 1 HumanMessage for the current turn, "
        f"got {len(human_messages)} (duplication bug)"
    )


# ── D4: invalid session_id must raise error, not create replacement ──────


@pytest.mark.asyncio
async def test_missing_session_id_must_not_create_replacement_session(
    mock_session_repo: AsyncMock,
) -> None:
    """SessionResolver must propagate SessionNotFoundError
    instead of creating a replacement session."""
    from modules.agent.application.handlers.session_resolver import SessionResolver

    resolver = SessionResolver(mock_session_repo)
    with pytest.raises(SessionNotFoundError):
        await resolver.resolve(
            project_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            tenant_id=None,
            user_id=None,
            session_mode="stateful",
        )
    assert mock_session_repo.create.call_count == 0
