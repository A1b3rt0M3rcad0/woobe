from __future__ import annotations

from enum import StrEnum, auto


class SessionStatus(StrEnum):
    ACTIVE = auto()
    WAITING = auto()
    IDLE = auto()
    CLOSED = auto()
    EXPIRED = auto()
    ERROR = auto()


class MessageRole(StrEnum):
    SYSTEM = auto()
    USER = auto()
    ASSISTANT = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()


class SessionMode(StrEnum):
    CHAT = auto()
    WORKFLOW = auto()
    AUTONOMOUS = auto()
    BACKGROUND = auto()
