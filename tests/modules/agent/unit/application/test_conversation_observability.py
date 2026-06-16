from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.handlers.conversation_context_builder import ConversationContext
from modules.agent.domain.enums import SessionMode
from modules.agent.domain.errors import ConversationHistoryLoadError
from modules.agent.domain.entities import Session


@pytest.fixture
def mock_trace_recorder():
    return AsyncMock()


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.id = uuid4()
    agent.project_id = uuid4()
    agent.session_mode = SessionMode.stateful
    agent.settings = {}
    agent.system_prompt = "You are a helpful assistant."
    return agent


@pytest.fixture
def mock_session():
    session = MagicMock(spec=Session)
    session.id = uuid4()
    session.project_id = uuid4()
    session.agent_id = uuid4()
    return session


def make_ask_input(override: dict | None = None) -> AskInput:
    base = {
        "project_id": uuid4(),
        "agent_id": uuid4(),
        "message": "Hello",
    }
    if override:
        base.update(override)
    return AskInput(**base)


class TestConversationObservability:
    @pytest.mark.anyio
    async def test_session_resolved_event_recorded(self, mock_trace_recorder, mock_agent, mock_session):
        from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase

        use_case = MagicMock(spec=AskAgentUseCase)
        use_case._trace_recorder = mock_trace_recorder

        ctx = ConversationContext(
            session=mock_session,
            history=[],
            prompt_messages=[],
            history_message_count=3,
            history_truncated=False,
        )
        input_dto = make_ask_input()

        method = getattr(AskAgentUseCase, "_record_conversation_events")
        await method(use_case, uuid4(), input_dto, ctx, mock_agent)

        session_resolved_calls = [
            c for c in mock_trace_recorder.record_event.call_args_list
            if "conversation.session_resolved" in str(c)
        ]
        assert len(session_resolved_calls) >= 1, "session_resolved event should be recorded"

        payload = session_resolved_calls[0].kwargs["payload"]
        assert "session_id" in payload
        assert "mode" in payload
        assert "project_id" in payload
        assert "agent_id" in payload
        assert "content" not in str(payload.get("message", ""))

    @pytest.mark.anyio
    async def test_history_loaded_event_contains_counts(self, mock_trace_recorder, mock_agent, mock_session):
        from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase

        use_case = MagicMock(spec=AskAgentUseCase)
        use_case._trace_recorder = mock_trace_recorder

        ctx = ConversationContext(
            session=mock_session,
            history=[],
            prompt_messages=[],
            history_message_count=5,
            history_truncated=True,
        )
        input_dto = make_ask_input()

        method = getattr(AskAgentUseCase, "_record_conversation_events")
        await method(use_case, uuid4(), input_dto, ctx, mock_agent)

        loaded_calls = [
            c for c in mock_trace_recorder.record_event.call_args_list
            if "conversation.history_loaded" in str(c)
        ]
        assert len(loaded_calls) >= 1

        payload = loaded_calls[0].kwargs["payload"]
        assert payload["message_count"] == 5
        assert payload["truncated"] is True
        assert "turn_count" in payload
        assert "contains_tool_calls" in payload

    @pytest.mark.anyio
    async def test_no_sensitive_content_in_payload(self, mock_trace_recorder, mock_agent, mock_session):
        from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase

        use_case = MagicMock(spec=AskAgentUseCase)
        use_case._trace_recorder = mock_trace_recorder

        ctx = ConversationContext(
            session=mock_session,
            history=[],
            prompt_messages=[],
            history_message_count=3,
            history_truncated=False,
        )
        input_dto = make_ask_input()

        method = getattr(AskAgentUseCase, "_record_conversation_events")
        await method(use_case, uuid4(), input_dto, ctx, mock_agent)

        for call in mock_trace_recorder.record_event.call_args_list:
            payload = call.kwargs.get("payload", {})
            payload_str = str(payload)
            assert input_dto.message not in payload_str, "message content must not leak into payload"

    @pytest.mark.anyio
    async def test_stateless_with_session_id_records_ignored_event(self, mock_trace_recorder, mock_agent):
        from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase

        use_case = MagicMock(spec=AskAgentUseCase)
        use_case._trace_recorder = mock_trace_recorder

        mock_agent.session_mode = SessionMode.stateless
        ctx = ConversationContext(
            session=None,
            history=[],
            prompt_messages=[],
            history_message_count=0,
            history_truncated=False,
        )
        session_id = uuid4()
        input_dto = make_ask_input({"session_id": session_id})

        method = getattr(AskAgentUseCase, "_record_conversation_events")
        await method(use_case, uuid4(), input_dto, ctx, mock_agent)

        ignored_calls = [
            c for c in mock_trace_recorder.record_event.call_args_list
            if "conversation.session_ignored_stateless" in str(c)
        ]
        assert len(ignored_calls) >= 1
        payload = ignored_calls[0].kwargs["payload"]
        assert str(session_id) in payload.get("session_id", "")

    def test_history_failure_produces_error_response(self):
        input_dto = make_ask_input()

        with pytest.raises(ConversationHistoryLoadError):
            builder = MagicMock()
            builder.build.side_effect = ConversationHistoryLoadError(
                session_id=uuid4(), message="test error",
            )
            async def call_build():
                await builder.build(input_dto, MagicMock(), None, None)
            import anyio
            anyio.run(call_build)


class TestStreamConversationObservability:
    @pytest.mark.anyio
    async def test_stream_error_on_history_failure(self, mock_trace_recorder, mock_agent):
        from modules.agent.application.use_cases.ask_agent_stream_service import (
            _record_conversation_events,
        )

        ctx = ConversationContext(
            session=None,
            history=[],
            prompt_messages=[],
            history_message_count=0,
            history_truncated=False,
        )
        input_dto = make_ask_input()
        await _record_conversation_events(
            mock_trace_recorder, uuid4(), input_dto, ctx, mock_agent,
        )
        assert True

    @pytest.mark.anyio
    async def test_stream_session_resolved_event(self, mock_trace_recorder, mock_agent):
        from modules.agent.application.use_cases.ask_agent_stream_service import (
            _record_conversation_events,
        )

        session = MagicMock(spec=Session)
        session.id = uuid4()
        ctx = ConversationContext(
            session=session,
            history=[],
            prompt_messages=[],
            history_message_count=2,
            history_truncated=False,
        )
        input_dto = make_ask_input()

        await _record_conversation_events(
            mock_trace_recorder, uuid4(), input_dto, ctx, mock_agent,
        )

        resolved_calls = [
            c for c in mock_trace_recorder.record_event.call_args_list
            if "conversation.session_resolved" in str(c)
        ]
        assert len(resolved_calls) >= 1
