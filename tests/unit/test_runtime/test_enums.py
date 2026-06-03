from enum import StrEnum

from modules.runtime.domain.enums import MessageRole, SessionMode, SessionStatus


class TestSessionStatus:
    def test_values(self):
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.WAITING == "waiting"
        assert SessionStatus.IDLE == "idle"
        assert SessionStatus.CLOSED == "closed"
        assert SessionStatus.EXPIRED == "expired"
        assert SessionStatus.ERROR == "error"

    def test_is_strenum(self):
        assert issubclass(SessionStatus, StrEnum)

    def test_members(self):
        assert len(SessionStatus) == 6


class TestMessageRole:
    def test_values(self):
        assert MessageRole.SYSTEM == "system"
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.TOOL_CALL == "tool_call"
        assert MessageRole.TOOL_RESULT == "tool_result"

    def test_is_strenum(self):
        assert issubclass(MessageRole, StrEnum)

    def test_members(self):
        assert len(MessageRole) == 5


class TestSessionMode:
    def test_values(self):
        assert SessionMode.CHAT == "chat"
        assert SessionMode.WORKFLOW == "workflow"
        assert SessionMode.AUTONOMOUS == "autonomous"
        assert SessionMode.BACKGROUND == "background"

    def test_is_strenum(self):
        assert issubclass(SessionMode, StrEnum)

    def test_members(self):
        assert len(SessionMode) == 4
