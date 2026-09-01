"""Agent inbox handlers — routes inbox events to application layer handlers."""
from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


class AgentInboxEventRouter:
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
