from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


class RuntimeStrategyConversation:
    """Read-only Strategy view over the real messages bound to one execution."""

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
            self._base_messages[current_user_index]
            if current_user_index is not None
            else None
        )
        history_end = (
            current_user_index
            if current_user_index is not None
            else len(self._base_messages)
        )
        self._history = tuple(
            message
            for message in self._base_messages[:history_end]
            if isinstance(message, (HumanMessage, AIMessage))
        )
        self._system_messages = tuple(
            message
            for message in self._base_messages
            if isinstance(message, SystemMessage)
        )

    @property
    def messages(self) -> tuple[Any, ...]:
        return tuple(self._runtime_state.messages)

    @property
    def current_user_message(self) -> Any | None:
        return self._current_user_message

    @property
    def history(self) -> tuple[Any, ...]:
        return self._history

    @property
    def system_messages(self) -> tuple[Any, ...]:
        return self._system_messages

    @property
    def assistant_messages(self) -> tuple[Any, ...]:
        return tuple(
            message
            for message in self._runtime_state.messages
            if isinstance(message, AIMessage)
        )

    @property
    def last_assistant_message(self) -> Any | None:
        for message in reversed(self._runtime_state.messages):
            if isinstance(message, AIMessage):
                return message
        return None
