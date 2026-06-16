"""Agent inbox handlers — routes inbox events to application layer handlers."""
from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


async def _handle_tool_created(
    event_type: str,
    payload: dict[str, Any],
    **kwargs: Any,
) -> None:
    logger.info("Tool created event received: %s", payload.get("aggregate_id"))


async def _handle_tool_updated(
    event_type: str,
    payload: dict[str, Any],
    **kwargs: Any,
) -> None:
    logger.info("Tool updated event received: %s", payload.get("aggregate_id"))


async def _handle_tool_status_changed(
    event_type: str,
    payload: dict[str, Any],
    **kwargs: Any,
) -> None:
    logger.info("Tool status changed event received: %s", payload.get("aggregate_id"))


async def _handle_secret_created(
    event_type: str,
    payload: dict[str, Any],
    **kwargs: Any,
) -> None:
    logger.info("Secret created event received: %s", payload.get("aggregate_id"))


AGENT_TOOL_EVENT_HANDLERS: dict[str, EventHandler] = {
    "agent.tool.created.v1": _handle_tool_created,
    "agent.tool.updated.v1": _handle_tool_updated,
    "agent.tool.status_changed.v1": _handle_tool_status_changed,
    "agent.secret.created.v1": _handle_secret_created,
}

TOOLS_LEGACY_EVENT_MAP: dict[str, str] = {
    "tools.tool.created": "agent.tool.created.v1",
    "tools.tool.updated": "agent.tool.updated.v1",
    "tools.tool.status_changed": "agent.tool.status_changed.v1",
    "tools.secret.created": "agent.secret.created.v1",
}


class AgentInboxEventRouter:
    def __init__(self, handlers: dict[str, EventHandler] | None = None) -> None:
        self._handlers: dict[str, EventHandler] = handlers or {}

    def register(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type] = handler

    def register_tool_handlers(self) -> None:
        for event_type, handler in AGENT_TOOL_EVENT_HANDLERS.items():
            self._handlers[event_type] = handler
        for legacy_type in TOOLS_LEGACY_EVENT_MAP:
            agent_type = TOOLS_LEGACY_EVENT_MAP[legacy_type]
            agent_handler = self._handlers.get(agent_type)
            if agent_handler:
                self._handlers[legacy_type] = agent_handler

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
