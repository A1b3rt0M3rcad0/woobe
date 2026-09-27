from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from modules.agent.application.strategy_sdk.tools import StrategyToolCall


class StrategyMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class StrategyMessage:
    """Framework-neutral conversation message exposed to Execution Strategies."""

    id: str | None
    role: StrategyMessageRole
    content: Any
    tool_calls: tuple[StrategyToolCall, ...] = ()
    tool_call_id: str | None = None


class StrategyConversation(Protocol):
    """Read-only framework-neutral conversation view exposed to an Execution Strategy."""

    @property
    def messages(self) -> tuple[StrategyMessage, ...]: ...

    @property
    def current_user_message(self) -> StrategyMessage | None: ...

    @property
    def history(self) -> tuple[StrategyMessage, ...]: ...

    @property
    def system_messages(self) -> tuple[StrategyMessage, ...]: ...

    @property
    def assistant_messages(self) -> tuple[StrategyMessage, ...]: ...

    @property
    def last_assistant_message(self) -> StrategyMessage | None: ...
