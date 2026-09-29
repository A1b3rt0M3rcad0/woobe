from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from modules.agent.application.strategy_sdk import (
    StrategyMessage,
    StrategyMessageRole,
    StrategyToolCall,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


def _tool_call(value: object) -> StrategyToolCall | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    args = value.get("args")
    if not isinstance(args, dict):
        args = {}
    call_id = value.get("id")
    return StrategyToolCall(
        id=str(call_id) if call_id is not None else None,
        name=name,
        arguments=args,
    )


def _strategy_message(message: Any) -> StrategyMessage:
    if isinstance(message, SystemMessage):
        role = StrategyMessageRole.SYSTEM
    elif isinstance(message, HumanMessage):
        role = StrategyMessageRole.USER
    elif isinstance(message, AIMessage):
        role = StrategyMessageRole.ASSISTANT
    elif isinstance(message, ToolMessage):
        role = StrategyMessageRole.TOOL
    else:
        role = StrategyMessageRole.OTHER

    raw_calls = getattr(message, "tool_calls", None) or ()
    calls = tuple(
        call
        for value in raw_calls
        if (call := _tool_call(value)) is not None
    )
    raw_id = getattr(message, "id", None)
    tool_call_id = getattr(message, "tool_call_id", None)
    return StrategyMessage(
        id=str(raw_id) if raw_id is not None else None,
        role=role,
        content=getattr(message, "content", None),
        tool_calls=calls,
        tool_call_id=str(tool_call_id) if tool_call_id is not None else None,
    )


class RuntimeStrategyConversation:
    """Read-only framework-neutral Strategy view over one execution conversation."""

    __slots__ = (
        "_runtime_state",
        "_base_messages",
        "_current_user_message",
        "_history",
        "_system_messages",
    )

    def __init__(
        self,
        *,
        runtime_state: StrategyRuntimeState,
        base_messages: list[Any],
    ) -> None:
        self._runtime_state = runtime_state
        self._base_messages = tuple(base_messages)

        current_user_index: int | None = None
        for index in range(len(self._base_messages) - 1, -1, -1):
            if isinstance(self._base_messages[index], HumanMessage):
                current_user_index = index
                break

        self._current_user_message = (
            _strategy_message(self._base_messages[current_user_index])
            if current_user_index is not None
            else None
        )
        history_end = (
            current_user_index
            if current_user_index is not None
            else len(self._base_messages)
        )
        self._history = tuple(
            _strategy_message(message)
            for message in self._base_messages[:history_end]
            if isinstance(message, (HumanMessage, AIMessage))
        )
        self._system_messages = tuple(
            _strategy_message(message)
            for message in self._base_messages
            if isinstance(message, SystemMessage)
        )

    @property
    def messages(self) -> tuple[StrategyMessage, ...]:
        return tuple(_strategy_message(message) for message in self._runtime_state.messages)

    @property
    def current_user_message(self) -> StrategyMessage | None:
        return self._current_user_message

    @property
    def history(self) -> tuple[StrategyMessage, ...]:
        return self._history

    @property
    def system_messages(self) -> tuple[StrategyMessage, ...]:
        return self._system_messages

    @property
    def assistant_messages(self) -> tuple[StrategyMessage, ...]:
        return tuple(
            _strategy_message(message)
            for message in self._runtime_state.messages
            if isinstance(message, AIMessage)
        )

    @property
    def last_assistant_message(self) -> StrategyMessage | None:
        for message in reversed(self._runtime_state.messages):
            if isinstance(message, AIMessage):
                return _strategy_message(message)
        return None
