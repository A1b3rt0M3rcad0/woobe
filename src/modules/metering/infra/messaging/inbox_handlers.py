from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]

HANDLED_EVENTS: dict[str, str] = {
    "agent.execution.requested.v1": "handle_execution_requested",
    "agent.execution.started.v1": "handle_execution_started",
    "agent.execution.llm_completed.v1": "handle_llm_request",
    "agent.execution.tool_completed.v1": "handle_tool_execution",
    "agent.execution.fallback_triggered.v1": "handle_fallback",
    "agent.execution.completed.v1": "handle_execution_completed",
    "agent.execution.failed.v1": "handle_execution_failed",
}


class MeteringInboxEventRouter:
    def __init__(self, handlers: dict[str, EventHandler] | None = None) -> None:
        self._handlers: dict[str, EventHandler] = handlers or {}

    def register(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type] = handler

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        handler = self._handlers.get(event_type)
        if handler is None:
            logger.warning(
                "No handler registered for event_type=%s, skipping",
                event_type,
            )
            return
        await handler(event_type=event_type, payload=payload, **kwargs)

    @property
    def registered_event_types(self) -> list[str]:
        return list(self._handlers.keys())
