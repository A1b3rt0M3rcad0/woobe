from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.infra.database.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


def _get_trace_id(payload: dict) -> UUID | None:
    raw = payload.get("trace_id") or payload.get("execution_id")
    if raw:
        return UUID(raw) if isinstance(raw, str) else raw
    return None


def _get_project_id(payload: dict) -> UUID | None:
    raw = payload.get("project_id")
    if raw:
        return UUID(raw) if isinstance(raw, str) else raw
    return None


def _get_agent_id(payload: dict) -> UUID | None:
    raw = payload.get("agent_id")
    if raw:
        return UUID(raw) if isinstance(raw, str) else raw
    return None


async def _get_or_create_trace(
    trace_repo: SQLAlchemyTraceRepository,
    trace_id: UUID,
    project_id: UUID | None,
    agent_id: UUID | None,
) -> Trace:
    trace = await trace_repo.get_by_id(trace_id)
    if trace is None:
        trace = Trace(
            id=trace_id,
            project_id=project_id or UUID(int=0),
            agent_id=agent_id,
            status=TraceStatus.pending,
            data={},
        )
    return trace


async def handle_trace_started(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    trace_id = _get_trace_id(payload)
    if trace_id is None:
        logger.warning("trace_started without trace_id")
        return

    trace = Trace(
        id=trace_id,
        project_id=_get_project_id(payload) or UUID(int=0),
        agent_id=_get_agent_id(payload),
        session_id=payload.get("session_id"),
        status=TraceStatus.running,
        started_at=datetime.now(timezone.utc),
        provider=payload.get("provider"),
        model=payload.get("model"),
        data={"event_type": event_type},
    )
    await trace_repo.save(trace)
    logger.info("Trace started: %s", trace_id)


async def handle_llm_call(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    event_repo = SQLAlchemyTraceEventRepository(session)
    trace_id = _get_trace_id(payload)
    if trace_id is None:
        return

    project_id = _get_project_id(payload) or UUID(int=0)
    trace = await _get_or_create_trace(trace_repo, trace_id, project_id, _get_agent_id(payload))
    trace.provider = payload.get("provider") or trace.provider
    trace.model = payload.get("model") or trace.model
    trace.data = trace.data or {}
    trace.data["input_tokens"] = payload.get("input_tokens")
    trace.data["output_tokens"] = payload.get("output_tokens")
    trace.total_cost_usd = (trace.total_cost_usd or 0) + float(payload.get("cost_usd", 0))
    await trace_repo.save(trace)

    event = TraceEvent(
        trace_id=trace_id,
        project_id=project_id,
        event_type=TraceEventType.llm_call,
        latency_ms=payload.get("latency_ms"),
        cost_usd=payload.get("cost_usd"),
        payload={
            "input_tokens": payload.get("input_tokens"),
            "output_tokens": payload.get("output_tokens"),
            "model": payload.get("model"),
        },
    )
    await event_repo.save(event)
    logger.info("LLM call recorded for trace=%s", trace_id)


async def handle_tool_call(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    event_repo = SQLAlchemyTraceEventRepository(session)
    trace_id = _get_trace_id(payload)
    if trace_id is None:
        return

    project_id = _get_project_id(payload) or UUID(int=0)
    trace = await _get_or_create_trace(trace_repo, trace_id, project_id, _get_agent_id(payload))
    trace.data = trace.data or {}
    trace.data["tool_calls"] = (trace.data.get("tool_calls", 0)) + 1
    await trace_repo.save(trace)

    event = TraceEvent(
        trace_id=trace_id,
        project_id=project_id,
        event_type=TraceEventType.tool_call,
        latency_ms=payload.get("latency_ms"),
        cost_usd=payload.get("cost_usd"),
        payload={
            "tool_id": payload.get("tool_id"),
            "tool_name": payload.get("tool_name"),
        },
    )
    await event_repo.save(event)
    logger.info("Tool call recorded for trace=%s, tool=%s", trace_id, payload.get("tool_name"))


async def handle_trace_fallback(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    trace_id = _get_trace_id(payload)
    if trace_id is None:
        return

    project_id = _get_project_id(payload) or UUID(int=0)
    trace = await _get_or_create_trace(trace_repo, trace_id, project_id, _get_agent_id(payload))
    trace.fallback_used = True
    trace.data = trace.data or {}
    trace.data["fallback_triggered"] = True
    await trace_repo.save(trace)
    logger.info("Fallback triggered for trace=%s", trace_id)


async def handle_trace_completed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    trace_id = _get_trace_id(payload)
    if trace_id is None:
        return

    project_id = _get_project_id(payload) or UUID(int=0)
    trace = await _get_or_create_trace(trace_repo, trace_id, project_id, _get_agent_id(payload))
    trace.status = TraceStatus.completed
    trace.ended_at = datetime.now(timezone.utc)
    trace.total_cost_usd = payload.get("total_cost_usd") or trace.total_cost_usd
    trace.total_latency_ms = payload.get("total_latency_ms") or trace.total_latency_ms
    trace.data = trace.data or {}
    trace.data["completed"] = True
    await trace_repo.save(trace)
    logger.info("Trace completed: %s", trace_id)


async def handle_trace_failed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    trace_id = _get_trace_id(payload)
    if trace_id is None:
        return

    project_id = _get_project_id(payload) or UUID(int=0)
    trace = await _get_or_create_trace(trace_repo, trace_id, project_id, _get_agent_id(payload))
    trace.status = TraceStatus.failed
    trace.ended_at = datetime.now(timezone.utc)
    trace.error = payload.get("error") or "unknown error"
    trace.data = trace.data or {}
    trace.data["failed"] = True
    await trace_repo.save(trace)
    logger.info("Trace failed: %s, error=%s", trace_id, trace.error)


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
