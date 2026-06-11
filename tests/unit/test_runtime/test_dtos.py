import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from modules.runtime.domain.enums import MessageRole, SessionMode, SessionStatus
from modules.runtime.service.dtos import (
    CreateSessionInput,
    CreateSessionOutput,
    MessageResponse,
    SendMessageInput,
    SendMessageOutput,
    ToolCallInfo,
)


class TestCreateSessionInput:
    def test_valid(self):
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        dto = CreateSessionInput(project_id=pid, agent_id=aid)
        assert dto.project_id == pid
        assert dto.agent_id == aid
        assert dto.mode == SessionMode.CHAT
        assert dto.data is None
        assert dto.external_session_id is None
        assert dto.tenant_id is None
        assert dto.user_id is None

    def test_with_all_fields(self):
        dto = CreateSessionInput(
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            external_session_id="ext-001",
            tenant_id="tenant1",
            user_id="user1",
            mode=SessionMode.WORKFLOW,
            data={"key": "val"},
        )
        assert dto.external_session_id == "ext-001"
        assert dto.tenant_id == "tenant1"
        assert dto.user_id == "user1"
        assert dto.mode == SessionMode.WORKFLOW
        assert dto.data == {"key": "val"}


class TestCreateSessionOutput:
    def test_valid(self):
        now = datetime.now(timezone.utc)
        dto = CreateSessionOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            external_session_id=None,
            tenant_id=None,
            user_id=None,
            status=SessionStatus.ACTIVE,
            mode=SessionMode.CHAT,
            data=None,
            last_message_at=None,
            created_at=now,
            updated_at=now,
        )
        assert dto.status == SessionStatus.ACTIVE
        assert dto.mode == SessionMode.CHAT

    def test_with_optional_fields(self):
        now = datetime.now(timezone.utc)
        dto = CreateSessionOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            external_session_id="ext-001",
            tenant_id="t1",
            user_id="u1",
            status=SessionStatus.ACTIVE,
            mode=SessionMode.CHAT,
            data={"env": "test"},
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        assert dto.external_session_id == "ext-001"
        assert dto.data == {"env": "test"}


class TestSendMessageInput:
    def test_valid(self):
        sid = uuid.uuid4()
        dto = SendMessageInput(session_id=sid, content="Hello")
        assert dto.session_id == sid
        assert dto.content == "Hello"
        assert dto.role == MessageRole.USER
        assert dto.data is None

    def test_with_role_and_metadata(self):
        dto = SendMessageInput(
            session_id=uuid.uuid4(),
            role=MessageRole.ASSISTANT,
            content="Response",
            data={"model": "gpt-4"},
        )
        assert dto.role == MessageRole.ASSISTANT
        assert dto.data == {"model": "gpt-4"}

    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            SendMessageInput(session_id=uuid.uuid4(), content="")


class TestMessageResponse:
    def test_valid(self):
        now = datetime.now(timezone.utc)
        dto = MessageResponse(
            id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            role=MessageRole.ASSISTANT,
            content="Hello",
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.001,
            data={"model": "gpt-4"},
            created_at=now,
            updated_at=now,
        )
        assert dto.content == "Hello"
        assert dto.role == MessageRole.ASSISTANT
        assert dto.cost_usd == 0.001
        assert dto.data == {"model": "gpt-4"}

    def test_optional_fields(self):
        now = datetime.now(timezone.utc)
        dto = MessageResponse(
            id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            role=MessageRole.USER,
            content="Hi",
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
            data=None,
            created_at=now,
            updated_at=now,
        )
        assert dto.input_tokens is None
        assert dto.output_tokens is None
        assert dto.cost_usd is None


class TestSendMessageOutput:
    def test_valid(self):
        now = datetime.now(timezone.utc)
        sid = uuid.uuid4()
        msg = MessageResponse(
            id=uuid.uuid4(),
            session_id=sid,
            role=MessageRole.USER,
            content="Hello",
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
            data=None,
            created_at=now,
            updated_at=now,
        )
        dto = SendMessageOutput(message=msg, session_id=sid)
        assert dto.message.content == "Hello"
        assert dto.session_id == sid


class TestToolCallInfo:
    def test_minimal(self):
        info = ToolCallInfo(tool_name="weather")
        assert info.tool_name == "weather"
        assert info.input is None
        assert info.output is None
        assert info.duration_ms is None
        assert info.success is True
        assert info.error is None

    def test_with_success(self):
        info = ToolCallInfo(
            tool_name="search",
            input={"q": "hello"},
            output={"results": ["a"]},
            duration_ms=1200,
            success=True,
            error=None,
        )
        assert info.tool_name == "search"
        assert info.input == {"q": "hello"}
        assert info.success is True
        assert info.error is None

    def test_with_failure(self):
        info = ToolCallInfo(
            tool_name="db_query",
            input={"sql": "SELECT *"},
            output={"error": "timeout"},
            duration_ms=30000,
            success=False,
            error="Connection timed out",
        )
        assert info.tool_name == "db_query"
        assert info.success is False
        assert info.error == "Connection timed out"
        assert info.duration_ms == 30000

    def test_model_dump_includes_new_fields(self):
        info = ToolCallInfo(
            tool_name="test",
            success=False,
            error="something broke",
        )
        dumped = info.model_dump()
        assert dumped["tool_name"] == "test"
        assert dumped["success"] is False
        assert dumped["error"] == "something broke"
