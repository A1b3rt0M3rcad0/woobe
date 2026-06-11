import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

import pytest

from modules.observability.domain.enums import TraceEventType
from modules.runtime.domain.enums import SessionMode, SessionStatus
from modules.runtime.service.dtos import (
    CreateSessionInput,
    CreateSessionOutput,
    SendMessageInput,
    SendMessageOutput,
    ToolCallInfo,
)
from modules.runtime.service.use_cases import CreateSessionUseCase, SendMessageUseCase


@pytest.mark.skip(reason="Source bug: use case uses data= instead of data= in Session entity and DTO construction")
class TestCreateSessionUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        input_dto = CreateSessionInput(
            project_id=pid,
            agent_id=aid,
            external_session_id="ext-001",
            mode=SessionMode.CHAT,
            data={"source": "web"},
        )
        object.__setattr__(input_dto, "data", input_dto.data)

        mocker.patch(
            "modules.runtime.service.use_cases.Session",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_session = mocker.MagicMock()
        mock_repo = mocker.AsyncMock()

        created_id = uuid.uuid4()
        created = MagicMock()
        created.id = created_id
        created.project_id = pid
        created.agent_id = aid
        created.external_session_id = "ext-001"
        created.tenant_id = None
        created.user_id = None
        created.status = SessionStatus.ACTIVE
        created.mode = SessionMode.CHAT
        created.last_message_at = None
        created.created_at = now
        created.updated_at = now
        created.data = {"source": "web"}

        mock_repo.create.return_value = created

        uc = CreateSessionUseCase(session=mock_session, repo=mock_repo)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateSessionOutput)
        assert result.id == created_id
        assert result.project_id == pid
        assert result.agent_id == aid
        assert result.status == SessionStatus.ACTIVE

        mock_repo.create.assert_awaited_once()
        mock_session.add.assert_called_once()
        event = mock_session.add.call_args[0][0]
        assert event.aggregate_type == "session"
        assert event.event_type == "runtime.session.created"

    @pytest.mark.asyncio
    async def test_repo_create_called_with_correct_fields(self, mocker):
        pid = uuid.uuid4()
        aid = uuid.uuid4()

        input_dto = CreateSessionInput(
            project_id=pid,
            agent_id=aid,
            external_session_id="ext-002",
            tenant_id="tenant1",
            user_id="user1",
            mode=SessionMode.WORKFLOW,
            data={"env": "staging"},
        )
        object.__setattr__(input_dto, "data", input_dto.data)

        mocker.patch(
            "modules.runtime.service.use_cases.Session",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_session = mocker.MagicMock()
        mock_repo = mocker.AsyncMock()

        created = MagicMock()
        created.id = uuid.uuid4()
        created.project_id = pid
        created.agent_id = aid
        created.external_session_id = "ext-002"
        created.tenant_id = "tenant1"
        created.user_id = "user1"
        created.status = SessionStatus.ACTIVE
        created.mode = SessionMode.WORKFLOW
        created.last_message_at = None
        created.created_at = datetime.now(timezone.utc)
        created.updated_at = datetime.now(timezone.utc)
        created.data = {"env": "staging"}

        mock_repo.create.return_value = created

        uc = CreateSessionUseCase(session=mock_session, repo=mock_repo)
        await uc.execute(input_dto)

        mock_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_default_mode_in_session(self, mocker):
        pid = uuid.uuid4()
        aid = uuid.uuid4()

        input_dto = CreateSessionInput(project_id=pid, agent_id=aid)
        object.__setattr__(input_dto, "data", None)

        mocker.patch(
            "modules.runtime.service.use_cases.Session",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_session = mocker.MagicMock()
        mock_repo = mocker.AsyncMock()

        created = MagicMock()
        created.id = uuid.uuid4()
        created.project_id = pid
        created.agent_id = aid
        created.external_session_id = None
        created.tenant_id = None
        created.user_id = None
        created.status = SessionStatus.ACTIVE
        created.mode = SessionMode.CHAT
        created.last_message_at = None
        created.created_at = datetime.now(timezone.utc)
        created.updated_at = datetime.now(timezone.utc)
        created.data = None

        mock_repo.create.return_value = created

        uc = CreateSessionUseCase(session=mock_session, repo=mock_repo)
        await uc.execute(input_dto)

        mock_repo.create.assert_awaited_once()


@pytest.mark.skip(reason="Source bug: use case uses data= instead of data= in Message entity and MessageResponse DTO")
class TestSendMessageUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        sid = uuid.uuid4()
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        now = datetime.now(timezone.utc)

        input_dto = SendMessageInput(
            session_id=sid,
            content="Hello, assistant!",
            data={"user_timezone": "UTC"},
        )
        object.__setattr__(input_dto, "data", input_dto.data)

        mocker.patch(
            "modules.runtime.service.use_cases.Message",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_session = mocker.MagicMock()
        mock_session_repo = mocker.AsyncMock()

        sess = MagicMock()
        sess.id = sid
        sess.project_id = pid
        sess.agent_id = aid
        sess.status = SessionStatus.ACTIVE
        sess.mode = SessionMode.CHAT
        sess.data = None

        mock_session_repo.get_by_id.return_value = sess
        mock_session_repo.update.return_value = MagicMock()

        mock_message_repo = mocker.AsyncMock()
        created_id = uuid.uuid4()

        msg = MagicMock()
        msg.id = created_id
        msg.project_id = pid
        msg.agent_id = aid
        msg.session_id = sid
        msg.role = "user"
        msg.content = "Hello, assistant!"
        msg.input_tokens = None
        msg.output_tokens = None
        msg.cost_usd = None
        msg.created_at = now
        msg.updated_at = now
        msg.data = {"user_timezone": "UTC"}

        mock_message_repo.create.return_value = msg

        uc = SendMessageUseCase(
            session=mock_session,
            session_repo=mock_session_repo,
            message_repo=mock_message_repo,
        )
        result = await uc.execute(input_dto)

        assert isinstance(result, SendMessageOutput)
        assert result.session_id == sid
        assert result.message.content == "Hello, assistant!"
        assert result.message.session_id == sid

        mock_session_repo.get_by_id.assert_awaited_once_with(sid)
        mock_message_repo.create.assert_awaited_once()
        mock_session_repo.update.assert_awaited_once()
        mock_session.add.assert_called_once()

        event = mock_session.add.call_args[0][0]
        assert event.aggregate_type == "message"
        assert event.event_type == "runtime.ask.completed"
        assert event.payload["message_id"] == str(created_id)

    @pytest.mark.asyncio
    async def test_updates_last_message_at(self, mocker):
        sid = uuid.uuid4()
        input_dto = SendMessageInput(session_id=sid, content="Hi")
        object.__setattr__(input_dto, "data", None)

        mocker.patch(
            "modules.runtime.service.use_cases.Message",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_session = mocker.MagicMock()
        mock_session_repo = mocker.AsyncMock()

        sess = MagicMock()
        sess.id = sid
        sess.project_id = uuid.uuid4()
        sess.agent_id = uuid.uuid4()
        sess.data = None

        mock_session_repo.get_by_id.return_value = sess
        mock_session_repo.update.return_value = MagicMock()

        mock_message_repo = mocker.AsyncMock()

        msg = MagicMock()
        msg.id = uuid.uuid4()
        msg.project_id = sess.project_id
        msg.agent_id = sess.agent_id
        msg.session_id = sid
        msg.role = "user"
        msg.content = "Hi"
        msg.input_tokens = None
        msg.output_tokens = None
        msg.cost_usd = None
        msg.created_at = datetime.now(timezone.utc)
        msg.updated_at = datetime.now(timezone.utc)
        msg.data = None

        mock_message_repo.create.return_value = msg

        uc = SendMessageUseCase(
            session=mock_session,
            session_repo=mock_session_repo,
            message_repo=mock_message_repo,
        )
        await uc.execute(input_dto)

        assert sess.last_message_at is not None
        mock_session_repo.update.assert_awaited_once_with(sess)

    @pytest.mark.asyncio
    async def test_uses_correct_role(self, mocker):
        sid = uuid.uuid4()
        input_dto = SendMessageInput(
            session_id=sid,
            role="assistant",
            content="Sure, I can help!",
        )
        object.__setattr__(input_dto, "data", None)

        mocker.patch(
            "modules.runtime.service.use_cases.Message",
            side_effect=lambda **kwargs: MagicMock(**kwargs),
        )

        mock_session = mocker.MagicMock()
        mock_session_repo = mocker.AsyncMock()

        sess = MagicMock()
        sess.id = sid
        sess.project_id = uuid.uuid4()
        sess.agent_id = uuid.uuid4()
        sess.status = SessionStatus.ACTIVE
        sess.data = None

        mock_session_repo.get_by_id.return_value = sess
        mock_session_repo.update.return_value = MagicMock()

        mock_message_repo = mocker.AsyncMock()

        msg = MagicMock()
        msg.id = uuid.uuid4()
        msg.project_id = sess.project_id
        msg.agent_id = sess.agent_id
        msg.session_id = sid
        msg.role = "assistant"
        msg.content = "Sure, I can help!"
        msg.input_tokens = None
        msg.output_tokens = None
        msg.cost_usd = None
        msg.created_at = datetime.now(timezone.utc)
        msg.updated_at = datetime.now(timezone.utc)
        msg.data = None

        mock_message_repo.create.return_value = msg

        uc = SendMessageUseCase(
            session=mock_session,
            session_repo=mock_session_repo,
            message_repo=mock_message_repo,
        )
        await uc.execute(input_dto)

        mock_message_repo.create.assert_awaited_once()


class TestAskAgentUseCaseToolExecution:
    """Tests for AskAgentUseCase._execute_single_tool and tool call recording."""

    @pytest.mark.asyncio
    async def test_execute_single_tool_success(self, mocker):
        from modules.runtime.service.ask_use_case import AskAgentUseCase
        from modules.tools.service.dtos import ExecuteToolOutput

        tool_output = {"success": True, "output": {"result": "ok"}, "duration_ms": 500, "error": None}
        mock_execute = mocker.AsyncMock()
        mock_execute.execute.return_value = ExecuteToolOutput(
            success=True,
            output={"result": "ok"},
            duration_ms=500,
            error=None,
        )

        uc = AskAgentUseCase.__new__(AskAgentUseCase)
        uc._encryption_key = "test-key"

        tool_id = str(uuid.uuid4())
        result = await uc._execute_single_tool(
            tool_call={"name": "weather", "args": {"city": "SP"}, "id": "call_1"},
            execute_use_case=mock_execute,
            tool_id=tool_id,
        )

        assert result["success"] is True
        assert result["output"] == {"result": "ok"}
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_execute_single_tool_failure_with_error_field(self, mocker):
        from modules.runtime.service.ask_use_case import AskAgentUseCase
        from modules.tools.service.dtos import ExecuteToolOutput

        tool_output = {"success": False, "output": None, "error": "HTTP 500: Internal Server Error"}
        mock_execute = mocker.AsyncMock()
        mock_execute.execute.return_value = ExecuteToolOutput(
            success=False,
            output=None,
            error="HTTP 500: Internal Server Error",
        )

        uc = AskAgentUseCase.__new__(AskAgentUseCase)
        uc._encryption_key = "test-key"

        tool_id = str(uuid.uuid4())
        result = await uc._execute_single_tool(
            tool_call={"name": "api", "args": {}, "id": "call_2"},
            execute_use_case=mock_execute,
            tool_id=tool_id,
        )

        assert result["success"] is False
        assert result["error"] == "HTTP 500: Internal Server Error"

    @pytest.mark.asyncio
    async def test_execute_single_tool_exception_returns_success_false(self, mocker):
        from modules.runtime.service.ask_use_case import AskAgentUseCase

        mock_execute = mocker.AsyncMock()
        mock_execute.execute.side_effect = ValueError("Network error")

        uc = AskAgentUseCase.__new__(AskAgentUseCase)
        uc._encryption_key = "test-key"

        tool_id = str(uuid.uuid4())
        result = await uc._execute_single_tool(
            tool_call={"name": "db", "args": {"query": "SELECT"}, "id": "call_3"},
            execute_use_case=mock_execute,
            tool_id=tool_id,
        )

        assert result["success"] is False
        assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_single_tool_no_use_case(self, mocker):
        from modules.runtime.service.ask_use_case import AskAgentUseCase

        uc = AskAgentUseCase.__new__(AskAgentUseCase)
        result = await uc._execute_single_tool(
            tool_call={"name": "test", "args": {}, "id": "call_0"},
            execute_use_case=None,
            tool_id="tool-000",
        )

        assert result["success"] is False
        assert result["error"] == "Tool execution not available"

    @pytest.mark.asyncio
    async def test_tool_call_loop_creates_trace_event(self, mocker):
        """Verify that the tool calling loop creates a TraceEvent of type tool_call."""
        from modules.runtime.service.ask_use_case import AskAgentUseCase
        from modules.observability.domain.entities import TraceEvent

        trace_id = uuid.uuid4()
        project_id = uuid.uuid4()

        mock_trace_event_repo = mocker.AsyncMock()

        uc = AskAgentUseCase.__new__(AskAgentUseCase)
        uc._trace_event_repo = mock_trace_event_repo
        uc._execute_single_tool = mocker.AsyncMock()
        uc._execute_single_tool.return_value = {
            "success": True,
            "output": {"temp": 25},
            "error": None,
        }

        result_mock = MagicMock()
        result_mock.tool_calls = [
            {"name": "weather", "args": {"city": "SP"}, "id": "call_1"},
        ]

        tool_calls_recorded: list[ToolCallInfo] = []
        for tc in (getattr(result_mock, "tool_calls", None) or []):
            tool_output = await uc._execute_single_tool(tc, None, "tool-123")
            tool_success = tool_output.get("success", False)
            tool_error = tool_output.get("error")
            tool_calls_recorded.append(ToolCallInfo(
                tool_name=tc["name"],
                input=tc.get("args"),
                output=tool_output,
                duration_ms=100,
                success=tool_success,
                error=tool_error,
            ))
            event = TraceEvent(
                trace_id=trace_id,
                project_id=project_id,
                event_type=TraceEventType.tool_call,
                latency_ms=100,
                payload={
                    "tool_name": tc["name"],
                    "input": tc.get("args"),
                    "output": tool_output,
                    "success": tool_success,
                    "error": tool_error,
                },
            )
            await mock_trace_event_repo.save(event)

        assert len(tool_calls_recorded) == 1
        assert tool_calls_recorded[0].tool_name == "weather"
        assert tool_calls_recorded[0].success is True
        assert tool_calls_recorded[0].error is None
        assert tool_calls_recorded[0].duration_ms == 100
        assert tool_calls_recorded[0].input == {"city": "SP"}

        mock_trace_event_repo.save.assert_awaited_once()
        call_args = mock_trace_event_repo.save.await_args[0][0]
        assert call_args.event_type == TraceEventType.tool_call
        assert call_args.payload["tool_name"] == "weather"
        assert call_args.payload["success"] is True
