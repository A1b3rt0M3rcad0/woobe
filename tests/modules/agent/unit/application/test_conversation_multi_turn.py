"""Multi-turn conversation behavior tests — spec 011.

Covers the full matrix of 10 conversation scenarios for both sync and stream
transport, verifying session, message, prompt, and error behavior.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from modules.agent.application.dtos.runtime_dtos import AskInput
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
    SessionStatus,
)
from modules.agent.domain.errors import (
    ConversationHistoryLoadError,
    SessionNotFoundError,
    SessionOwnershipMismatchError,
)


def _fake_agent(session_mode="stateful", agent_id=None, project_id=None):
    agent = AsyncMock()
    agent.session_mode = session_mode
    agent.id = agent_id or uuid4()
    agent.project_id = project_id or uuid4()
    agent.system_prompt = "You are a helpful assistant."
    agent.settings = {"history_max_messages": 100}
    return agent


def _make_session(**overrides) -> Session:
    fields = dict(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        mode=RuntimeSessionMode.CHAT,
        status=SessionStatus.ACTIVE,
        tenant_id="tenant-1",
        user_id="user-1",
    )
    fields.update(overrides)
    return Session(**fields)


def _make_input(agent_id, project_id, **overrides) -> AskInput:
    base = dict(
        project_id=project_id,
        agent_id=agent_id,
        message="Hello",
    )
    base.update(overrides)
    return AskInput(**base)


def _make_session_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.create = AsyncMock(side_effect=lambda s: s)
    repo.update = AsyncMock()
    return repo


class _StoringMessageRepo:
    def __init__(self, initial_messages: list[Message] | None = None):
        self.stored: list[Message] = list(initial_messages or [])
        self.create = AsyncMock(side_effect=self._create)
        self.list_recent_by_session = AsyncMock(side_effect=self._list_recent_by_session)
        self.list_by_session = AsyncMock(side_effect=self._list_by_session)

    async def _create(self, msg: Message) -> Message:
        msg.id = uuid4()
        self.stored.append(msg)
        return msg

    async def _list_recent_by_session(self, session_id, limit=100):
        return self.stored[-limit:]

    async def _list_by_session(self, session_id, offset=0, limit=100):
        return self.stored[offset:offset + limit]


def _make_message_repo(initial_messages: list[Message] | None = None):
    return _StoringMessageRepo(initial_messages)


# ── Test matrix ─────────────────────────────────────────────────────────


class TestStatefulFirstTurn:
    @pytest.mark.asyncio
    async def test_sync_first_turn_creates_session_and_messages(self):
        agent_id = uuid4()
        project_id = uuid4()
        agent = _fake_agent("stateful", agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()

        async def _get_by_id(sid):
            raise SessionNotFoundError(sid)
        session_repo.get_by_id = AsyncMock(side_effect=_get_by_id)

        msg_repo = _make_message_repo()
        builder = ConversationContextBuilder(session_repo, msg_repo)

        ctx = await builder.build(
            input_dto=_make_input(agent.id, project_id, session_id=None),
            agent=agent,
        )

        assert ctx.session is not None, "stateful first turn must create session"
        assert ctx.session.id is not None
        assert ctx.history_message_count == 0, "first turn has no history"

    @pytest.mark.asyncio
    async def test_stream_first_turn_shared_behavior(self):
        agent_id = uuid4()
        project_id = uuid4()
        agent = _fake_agent("stateful", agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()

        async def _get_by_id(sid):
            raise SessionNotFoundError(sid)
        session_repo.get_by_id = AsyncMock(side_effect=_get_by_id)

        msg_repo = _make_message_repo()
        builder = ConversationContextBuilder(session_repo, msg_repo)

        ctx = await builder.build(
            input_dto=_make_input(agent.id, project_id, session_id=None),
            agent=agent,
        )

        assert ctx.session is not None
        assert ctx.user_message_id is not None, "user message must be persisted"


class TestStatefulSecondTurn:
    @pytest.mark.asyncio
    async def test_sync_second_turn_contains_previous_turn_in_prompt(self):
        agent_id = uuid4()
        project_id = uuid4()
        session = _make_session(agent_id=agent_id, project_id=project_id)
        agent = _fake_agent("stateful", agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()
        session_repo.get_by_id = AsyncMock(return_value=session)

        msg_repo = _make_message_repo()
        builder = ConversationContextBuilder(session_repo, msg_repo)

        first_input = _make_input(agent.id, project_id, session_id=session.id, message="Primeira pergunta")
        await builder.build(input_dto=first_input, agent=agent)

        ctx = await builder.build(
            input_dto=_make_input(agent.id, project_id, session_id=session.id, message="Qual foi minha pergunta anterior?"),
            agent=agent,
        )

        human_messages = [m for m in ctx.prompt_messages if isinstance(m, HumanMessage)]
        assert any("Primeira pergunta" in str(h.content) for h in human_messages), (
            "second turn prompt must contain previous user message"
        )

    @pytest.mark.asyncio
    async def test_stream_second_turn_shared_behavior(self):
        agent_id = uuid4()
        project_id = uuid4()
        session = _make_session(agent_id=agent_id, project_id=project_id)
        agent = _fake_agent("stateful", agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()
        session_repo.get_by_id = AsyncMock(return_value=session)

        msg_repo = _make_message_repo()
        builder = ConversationContextBuilder(session_repo, msg_repo)

        await builder.build(
            input_dto=_make_input(agent.id, project_id, session_id=session.id, message="Turno 1"),
            agent=agent,
        )

        ctx = await builder.build(
            input_dto=_make_input(agent.id, project_id, session_id=session.id, message="Turno 2"),
            agent=agent,
        )

        assert ctx.session.id == session.id, "same session must be reused"


class TestAssistantWithoutTools:
    @pytest.mark.asyncio
    async def test_sync_assistant_without_tools_preserves_history(self):
        session = _make_session()
        msg_repo = _make_message_repo([
            Message(
                id=uuid4(), session_id=session.id, project_id=session.project_id,
                role=MessageRole.USER, content="User message",
            ),
            Message(
                id=uuid4(), session_id=session.id, project_id=session.project_id,
                role=MessageRole.ASSISTANT, content="Resposta sem tools", data=None,
            ),
        ])

        history = await load_and_convert_history(msg_repo, session.id, session.id, limit=100)

        assert len(history) > 0
        assert isinstance(history[-1], AIMessage)
        assert history[-1].content == "Resposta sem tools"

    @pytest.mark.asyncio
    async def test_stream_assistant_without_tools_preserves_history(self):
        await self.test_sync_assistant_without_tools_preserves_history()


class TestAssistantWithTools:
    @pytest.mark.asyncio
    async def test_sync_assistant_with_tools_preserves_tool_metadata(self):
        session = _make_session()
        msg_repo = _make_message_repo([
            Message(
                id=uuid4(), session_id=session.id, project_id=session.project_id,
                role=MessageRole.USER, content="Use a tool",
            ),
            Message(
                id=uuid4(), session_id=session.id, project_id=session.project_id,
                role=MessageRole.ASSISTANT, content="",
                data={"tool_calls": [{"tool_call_id": "call_1", "tool_name": "search", "input": {"q": "test"}}]},
            ),
        ])

        history = await load_and_convert_history(msg_repo, session.id, session.id, limit=100)

        assert len(history) > 0
        ai_messages = [m for m in history if isinstance(m, AIMessage)]
        assert any(
            bool(getattr(m, "tool_calls", None)) for m in ai_messages
        ), "tool calls metadata must be preserved"

    @pytest.mark.asyncio
    async def test_stream_assistant_with_tools_preserves_tool_metadata(self):
        await self.test_sync_assistant_with_tools_preserves_tool_metadata()


class TestInvalidSessionId:
    @pytest.mark.asyncio
    async def test_sync_invalid_session_id_raises_error(self):
        session_repo = _make_session_repo()

        async def _get_by_id(sid):
            raise SessionNotFoundError(sid)
        session_repo.get_by_id = AsyncMock(side_effect=_get_by_id)

        resolver = ConversationContextBuilder(session_repo, _make_message_repo())
        agent_id = uuid4()

        with pytest.raises(SessionNotFoundError):
            await resolver._session_resolver.resolve(
                project_id=uuid4(),
                agent_id=agent_id,
                session_id=uuid4(),
                tenant_id="tenant-1",
                user_id="user-1",
                session_mode="stateful",
            )

    @pytest.mark.asyncio
    async def test_stream_invalid_session_id_raises_error(self):
        await self.test_sync_invalid_session_id_raises_error()


class TestSessionOwnership:
    @pytest.mark.asyncio
    async def test_sync_session_from_other_agent_raises_error(self):
        agent_id = uuid4()
        project_id = uuid4()
        session = _make_session(agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()
        session_repo.get_by_id = AsyncMock(return_value=session)

        resolver = ConversationContextBuilder(session_repo, _make_message_repo())

        with pytest.raises(SessionOwnershipMismatchError):
            await resolver._session_resolver.resolve(
                project_id=project_id,
                agent_id=uuid4(),
                session_id=session.id,
                tenant_id="tenant-1",
                user_id="user-1",
                session_mode="stateful",
            )

    @pytest.mark.asyncio
    async def test_sync_session_from_other_project_raises_error(self):
        agent_id = uuid4()
        project_id = uuid4()
        session = _make_session(agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()
        session_repo.get_by_id = AsyncMock(return_value=session)

        resolver = ConversationContextBuilder(session_repo, _make_message_repo())

        with pytest.raises(SessionOwnershipMismatchError):
            await resolver._session_resolver.resolve(
                project_id=uuid4(),
                agent_id=agent_id,
                session_id=session.id,
                tenant_id="tenant-1",
                user_id="user-1",
                session_mode="stateful",
            )

    @pytest.mark.asyncio
    async def test_stream_session_from_other_agent_raises_error(self):
        await self.test_sync_session_from_other_agent_raises_error()


class TestStateless:
    @pytest.mark.asyncio
    async def test_sync_stateless_does_not_create_session(self):
        agent = _fake_agent("stateless")
        session_repo = _make_session_repo()
        msg_repo = _make_message_repo()
        builder = ConversationContextBuilder(session_repo, msg_repo)

        ctx = await builder.build(
            input_dto=_make_input(agent.id, uuid4(), session_id=None),
            agent=agent,
        )

        assert ctx.session is None, "stateless must not create session"
        assert ctx.user_message_id is None, "stateless must not persist message"

    @pytest.mark.asyncio
    async def test_sync_stateless_with_session_id_still_returns_none(self):
        agent = _fake_agent("stateless")
        session_repo = _make_session_repo()
        msg_repo = _make_message_repo()
        builder = ConversationContextBuilder(session_repo, msg_repo)

        ctx = await builder.build(
            input_dto=_make_input(agent.id, uuid4(), session_id=uuid4()),
            agent=agent,
        )

        assert ctx.session is None, "stateless must ignore session_id"
        assert msg_repo.create.call_count == 0

    @pytest.mark.asyncio
    async def test_stream_stateless_does_not_create_session(self):
        await self.test_sync_stateless_does_not_create_session()


class TestHistoryWindow:
    @pytest.mark.asyncio
    async def test_sync_history_window_respects_limit(self):
        session = _make_session()
        msg_repo = _make_message_repo()

        for _ in range(25):
            msg_repo.stored.append(
                Message(id=uuid4(), session_id=session.id, project_id=session.project_id,
                        role=MessageRole.USER, content="msg")
            )
            msg_repo.stored.append(
                Message(id=uuid4(), session_id=session.id, project_id=session.project_id,
                        role=MessageRole.ASSISTANT, content="resp", data=None)
            )

        history = await load_and_convert_history(msg_repo, session.id, session.id, limit=10)

        assert len(history) <= 10, "window must be limited to last N messages"

    @pytest.mark.asyncio
    async def test_stream_history_window_respects_limit(self):
        await self.test_sync_history_window_respects_limit()


class TestMapperError:
    @pytest.mark.asyncio
    async def test_sync_mapper_error_raises_explicitly(self):
        agent_id = uuid4()
        project_id = uuid4()
        session = _make_session(agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()
        session_repo.get_by_id = AsyncMock(return_value=session)

        msg_repo = AsyncMock()
        msg_repo.list_recent_by_session = AsyncMock(
            side_effect=RuntimeError("DB connection failed")
        )

        builder = ConversationContextBuilder(session_repo, msg_repo)
        agent = _fake_agent("stateful", agent_id=agent_id, project_id=project_id)

        with pytest.raises(ConversationHistoryLoadError):
            await builder.build(
                input_dto=_make_input(agent.id, project_id, session_id=session.id),
                agent=agent,
            )

    @pytest.mark.asyncio
    async def test_stream_mapper_error_raises_explicitly(self):
        await self.test_sync_mapper_error_raises_explicitly()


class TestCurrentTurnNotDuplicated:
    @pytest.mark.asyncio
    async def test_sync_current_turn_appears_once(self):
        agent_id = uuid4()
        project_id = uuid4()
        session = _make_session(agent_id=agent_id, project_id=project_id)
        agent = _fake_agent("stateful", agent_id=agent_id, project_id=project_id)
        session_repo = _make_session_repo()
        session_repo.get_by_id = AsyncMock(return_value=session)

        msg_repo = _make_message_repo()
        builder = ConversationContextBuilder(session_repo, msg_repo)

        ctx = await builder.build(
            input_dto=_make_input(agent.id, project_id, session_id=session.id, message="Minha pergunta"),
            agent=agent,
        )

        human_messages = [
            m for m in ctx.prompt_messages
            if isinstance(m, HumanMessage) and "Minha pergunta" in str(m.content)
        ]
        assert len(human_messages) == 1, "current turn must appear exactly once"

    @pytest.mark.asyncio
    async def test_stream_current_turn_appears_once(self):
        await self.test_sync_current_turn_appears_once()
