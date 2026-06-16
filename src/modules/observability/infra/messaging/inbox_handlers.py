from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.domain.entities import Trace
from modules.observability.infra.database.repositories import SQLAlchemyTraceRepository

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


async def handle_trace_started(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping trace_started handler")
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    trace = Trace(
        project_id=payload.get("project_id"),
        agent_id=payload.get("agent_id"),
        session_id=payload.get("session_id"),
        status="started",
        data=payload,
    )
    await trace_repo.save(trace)
    logger.info("Trace started: %s", trace.id)


async def handle_llm_call(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping llm_call handler")
        return
    logger.info("LLM call recorded for execution_id=%s", payload.get("execution_id"))


async def handle_tool_call(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping tool_call handler")
        return
    logger.info("Tool call recorded for execution_id=%s, tool=%s", payload.get("execution_id"), payload.get("tool_name"))


async def handle_trace_fallback(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping trace_fallback handler")
        return
    logger.info("Fallback triggered for execution_id=%s", payload.get("execution_id"))


async def handle_trace_completed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping trace_completed handler")
        return
    logger.info("Trace completed for execution_id=%s", payload.get("execution_id"))


async def handle_trace_failed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        logger.warning("No session provided, skipping trace_failed handler")
        return
    logger.info("Trace failed for execution_id=%s, error=%s", payload.get("execution_id"), payload.get("error"))


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
            logger.warning(
                "No handler registered for event_type=%s, skipping",
                event_type,
            )
            return
        await handler(event_type=event_type, payload=payload, **kwargs)

    @property
    def registered_event_types(self) -> list[str]:
        return list(self._handlers.keys())
