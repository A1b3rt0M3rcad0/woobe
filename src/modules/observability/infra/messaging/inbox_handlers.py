from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.infra.messaging.trace_projector import project_agent_event

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


async def _project(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        raise RuntimeError("Observability Inbox handler requires a database session")
    await project_agent_event(
        event_type=event_type,
        payload=payload,
        session=session,
    )


handle_trace_started = _project
handle_llm_call = _project
handle_tool_call = _project
handle_trace_fallback = _project
handle_trace_completed = _project
handle_trace_failed = _project

HANDLER_MAP: dict[str, EventHandler] = {
    "agent.execution.started.v1": handle_trace_started,
    "agent.execution.llm_completed.v1": handle_llm_call,
    "agent.execution.tool_completed.v1": handle_tool_call,
    "agent.execution.fallback_triggered.v1": handle_trace_fallback,
    "agent.execution.completed.v1": handle_trace_completed,
    "agent.execution.failed.v1": handle_trace_failed,
}


class ObservabilityInboxEventRouter:
    def __init__(self, handlers: dict[str, EventHandler] | None = None) -> None:
        self._handlers: dict[str, EventHandler] = handlers or dict(HANDLER_MAP)

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
            logger.warning("No observability handler for event_type=%s", event_type)
            return
        await handler(event_type=event_type, payload=payload, **kwargs)

    @property
    def registered_event_types(self) -> list[str]:
        return list(self._handlers.keys())
