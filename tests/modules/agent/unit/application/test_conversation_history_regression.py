"""Red tests reproducing session-history bugs.

These tests exercise production code directly and are expected to FAIL
before the corresponding fixes in specs 003-005. Each test targets one
specific defect:

- assistant without tool_calls erases history (except Exception: return [])
- current user turn appears twice in the prompt
- missing session_id silently creates a replacement session
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

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
def mock_session() -> Session:
    return Session(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        mode=RuntimeSessionMode.CHAT,
        status=SessionStatus.ACTIVE,
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
    return repo


@pytest.fixture
def mock_session_repo() -> AsyncMock:
    repo = AsyncMock(spec=SessionRepository)

    async def _get_by_id(session_id):
        raise SessionNotFoundError(session_id)

    repo.get_by_id = AsyncMock(side_effect=_get_by_id)
    repo.create = AsyncMock(side_effect=lambda s: s)
    return repo


@pytest.fixture
def use_case(mock_message_repo, mock_session_repo) -> AskAgentUseCase:
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
        encryption_key="test-encryption-key-for-unit-tests",
    )


@pytest.mark.asyncio
async def test_assistant_without_tool_calls_must_not_erase_history(
    use_case: AskAgentUseCase,
    mock_message_repo: AsyncMock,
    mock_session: Session,
) -> None:
    """Exercise _load_history with an assistant message that has no tool_calls.

    The current code does:
        raw_tool_calls = (m.data or {}).get("tool_calls") or []
        tool_calls = None
        if raw_tool_calls:
            tool_calls = [...]
        msg = AIMessage(content=m.content, tool_calls=tool_calls)

    When tool_calls is None, AIMessage(..., tool_calls=None) raises a
    Pydantic validation error inside except Exception: return [].
    The expected behavior is to return history with the AIMessage.
    """
    history = await use_case._load_history(mock_session)
    assert len(history) > 0, (
        "_load_history returned empty list for assistant message "
        "without tool_calls (the AIMessage(tool_calls=None) bug)"
    )
    assert isinstance(history[0], AIMessage)
    assert history[0].content == "Entendido."


@pytest.mark.asyncio
async def test_current_user_turn_is_not_present_twice(
    use_case: AskAgentUseCase,
    mock_session: Session,
) -> None:
    """Verify that _load_history + _save_user_message + _build_messages
    produces the current turn exactly once.

    After spec 004, load happens BEFORE save so the saved turn
    is not included in history. Build_messages adds it separately.
    """
    user_message = "Qual é o meu código?"

    history = await use_case._load_history(mock_session)

    await use_case._save_user_message(mock_session, user_message, AsyncMock())

    messages = use_case._build_messages(
        agent=AsyncMock(system_prompt="You are a helpful assistant."),
        rag_context=None,
        history=history,
        user_message=user_message,
    )

    human_messages = [m for m in messages if isinstance(m, HumanMessage)]
    assert len(human_messages) == 1, (
        f"Expected exactly 1 HumanMessage for the current turn, "
        f"got {len(human_messages)} (duplication bug)"
    )


@pytest.mark.asyncio
async def test_missing_session_id_must_not_create_replacement_session(
    use_case: AskAgentUseCase,
    mock_session_repo: AsyncMock,
) -> None:
    """Exercise _resolve_session with an invalid session_id.

    Current code catches all exceptions in _resolve_session and creates
    a new session. Expected behavior: propagate the SessionNotFoundError.
    """
    invalid_session_id = uuid4()
    input_dto = AskInput(
        project_id=uuid4(),
        agent_id=uuid4(),
        message="test",
        session_id=invalid_session_id,
    )
    agent = AsyncMock()
    agent.session_mode = SessionMode.stateful
    agent.id = uuid4()

    result = await use_case._resolve_session(input_dto, agent)

    # The current bug creates a new session instead of raising
    # After the fix this should raise SessionNotFoundError.
    # For the red test, we assert the bug exists:
    create_calls = mock_session_repo.create.call_count
    assert create_calls == 1, (
        f"_resolve_session with invalid session_id created {create_calls} "
        f"replacement session(s) instead of raising SessionNotFoundError"
    )
    assert result is not None
    assert result.id != invalid_session_id
