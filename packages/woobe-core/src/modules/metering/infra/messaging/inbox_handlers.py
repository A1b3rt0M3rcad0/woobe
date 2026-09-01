from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any, Callable, Coroutine
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.metering.domain.entities import UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit
from modules.metering.infra.database.repositories import SQLAlchemyUsageEventRepository

logger = logging.getLogger(__name__)

EventHandler = Callable[..., Coroutine[Any, Any, None]]


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _required_uuid(payload: dict[str, Any], field: str) -> UUID:
    value = _uuid(payload.get(field))
    if value is None:
        raise ValueError(f"Metering event requires {field}")
    return value


def _occurred_at(payload: dict[str, Any]) -> datetime:
    raw = payload.get("occurred_at") or payload.get("ended_at") or payload.get("started_at")
    if isinstance(raw, datetime):
        value = raw
    elif isinstance(raw, str) and raw:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        value = datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _cost_request_deltas(cost_status: str | None) -> tuple[int, int, int]:
    normalized = str(cost_status or "unknown")
    if normalized == "known":
        return 1, 0, 0
    if normalized == "partial":
        return 0, 1, 0
    return 0, 0, 1


async def _increment_daily(
    session: AsyncSession,
    *,
    project_id: UUID,
    agent_id: UUID | None,
    day: date,
    occurred_at: datetime,
    requests: int = 0,
    successful_requests: int = 0,
    failed_requests: int = 0,
    cancelled_requests: int = 0,
    llm_calls: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tool_calls: int = 0,
    cost_usd: float = 0.0,
    priced_requests: int = 0,
    partial_cost_requests: int = 0,
    unpriced_requests: int = 0,
) -> None:
    params = {
        "project_id": project_id,
        "agent_id": agent_id,
        "day": day,
        "requests": requests,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "cancelled_requests": cancelled_requests,
        "llm_calls": llm_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tool_calls": tool_calls,
        "cost_usd": cost_usd,
        "priced_requests": priced_requests,
        "partial_cost_requests": partial_cost_requests,
        "unpriced_requests": unpriced_requests,
        "occurred_at": occurred_at,
        "updated_at": datetime.now(UTC),
    }
    await session.execute(
        text(
            """
            INSERT INTO metering.usage_daily_project (
                project_id, day, requests, successful_requests, failed_requests,
                cancelled_requests, llm_calls, input_tokens, output_tokens,
                embedding_tokens, tool_calls, vector_queries, storage_mb, cost_usd,
                priced_requests, partial_cost_requests, unpriced_requests,
                last_event_occurred_at, updated_at
            ) VALUES (
                :project_id, :day, :requests, :successful_requests, :failed_requests,
                :cancelled_requests, :llm_calls, :input_tokens, :output_tokens,
                0, :tool_calls, 0, 0, :cost_usd,
                :priced_requests, :partial_cost_requests, :unpriced_requests,
                :occurred_at, :updated_at
            )
            ON CONFLICT (project_id, day) DO UPDATE SET
                requests = metering.usage_daily_project.requests + EXCLUDED.requests,
                successful_requests = metering.usage_daily_project.successful_requests + EXCLUDED.successful_requests,
                failed_requests = metering.usage_daily_project.failed_requests + EXCLUDED.failed_requests,
                cancelled_requests = metering.usage_daily_project.cancelled_requests + EXCLUDED.cancelled_requests,
                llm_calls = metering.usage_daily_project.llm_calls + EXCLUDED.llm_calls,
                input_tokens = metering.usage_daily_project.input_tokens + EXCLUDED.input_tokens,
                output_tokens = metering.usage_daily_project.output_tokens + EXCLUDED.output_tokens,
                tool_calls = metering.usage_daily_project.tool_calls + EXCLUDED.tool_calls,
                cost_usd = metering.usage_daily_project.cost_usd + EXCLUDED.cost_usd,
                priced_requests = metering.usage_daily_project.priced_requests + EXCLUDED.priced_requests,
                partial_cost_requests = metering.usage_daily_project.partial_cost_requests + EXCLUDED.partial_cost_requests,
                unpriced_requests = metering.usage_daily_project.unpriced_requests + EXCLUDED.unpriced_requests,
                last_event_occurred_at = GREATEST(
                    metering.usage_daily_project.last_event_occurred_at,
                    EXCLUDED.last_event_occurred_at
                ),
                updated_at = EXCLUDED.updated_at
            """
        ),
        params,
    )
    if agent_id is None:
        return
    await session.execute(
        text(
            """
            INSERT INTO metering.usage_daily_agent (
                agent_id, day, project_id, requests, successful_requests,
                failed_requests, cancelled_requests, llm_calls, input_tokens,
                output_tokens, tool_calls, vector_queries, cost_usd,
                priced_requests, partial_cost_requests, unpriced_requests,
                last_event_occurred_at, updated_at
            ) VALUES (
                :agent_id, :day, :project_id, :requests, :successful_requests,
                :failed_requests, :cancelled_requests, :llm_calls, :input_tokens,
                :output_tokens, :tool_calls, 0, :cost_usd,
                :priced_requests, :partial_cost_requests, :unpriced_requests,
                :occurred_at, :updated_at
            )
            ON CONFLICT (agent_id, day) DO UPDATE SET
                requests = metering.usage_daily_agent.requests + EXCLUDED.requests,
                successful_requests = metering.usage_daily_agent.successful_requests + EXCLUDED.successful_requests,
                failed_requests = metering.usage_daily_agent.failed_requests + EXCLUDED.failed_requests,
                cancelled_requests = metering.usage_daily_agent.cancelled_requests + EXCLUDED.cancelled_requests,
                llm_calls = metering.usage_daily_agent.llm_calls + EXCLUDED.llm_calls,
                input_tokens = metering.usage_daily_agent.input_tokens + EXCLUDED.input_tokens,
                output_tokens = metering.usage_daily_agent.output_tokens + EXCLUDED.output_tokens,
                tool_calls = metering.usage_daily_agent.tool_calls + EXCLUDED.tool_calls,
                cost_usd = metering.usage_daily_agent.cost_usd + EXCLUDED.cost_usd,
                priced_requests = metering.usage_daily_agent.priced_requests + EXCLUDED.priced_requests,
                partial_cost_requests = metering.usage_daily_agent.partial_cost_requests + EXCLUDED.partial_cost_requests,
                unpriced_requests = metering.usage_daily_agent.unpriced_requests + EXCLUDED.unpriced_requests,
                last_event_occurred_at = GREATEST(
                    metering.usage_daily_agent.last_event_occurred_at,
                    EXCLUDED.last_event_occurred_at
                ),
                updated_at = EXCLUDED.updated_at
            """
        ),
        params,
    )


async def handle_noop(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    logger.debug("No-op handler for event_type=%s", event_type)


async def handle_llm_request(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        raise RuntimeError("Metering session is required")
    project_id = _required_uuid(payload, "project_id")
    agent_id = _uuid(payload.get("agent_id"))
    trace_id = _required_uuid(payload, "trace_id")
    occurred_at = _occurred_at(payload)
    input_tokens = _int_or_none(payload.get("input_tokens"))
    output_tokens = _int_or_none(payload.get("output_tokens"))
    cost = _float_or_none(payload.get("cost_usd"))
    source_event_id = _uuid(kwargs.get("source_event_id"))

    await SQLAlchemyUsageEventRepository(session).save(
        UsageEvent(
            project_id=project_id,
            agent_id=agent_id,
            source_event_id=source_event_id,
            occurred_at=occurred_at,
            trace_id=trace_id,
            call_id=str(payload.get("call_id")) if payload.get("call_id") else None,
            environment=payload.get("execution_context") or payload.get("environment"),
            agent_release_id=_uuid(payload.get("agent_release_id")),
            agent_release_version=payload.get("agent_release_version"),
            provider=payload.get("provider"),
            model=payload.get("model"),
            provider_model_id=_uuid(payload.get("provider_model_id")),
            event_type=UsageEventType.llm_request,
            quantity=float((input_tokens or 0) + (output_tokens or 0)),
            unit=UsageUnit.token,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            cost_status=str(payload.get("cost_status") or "unknown"),
            cost_reason=payload.get("cost_reason"),
            usage_complete=payload.get("usage_complete"),
            pricing_snapshot=payload.get("pricing_snapshot"),
            data=payload,
        )
    )
    await _increment_daily(
        session,
        project_id=project_id,
        agent_id=agent_id,
        day=occurred_at.date(),
        occurred_at=occurred_at,
        llm_calls=1,
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
        cost_usd=cost or 0.0,
    )


async def handle_tool_execution(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        raise RuntimeError("Metering session is required")
    project_id = _required_uuid(payload, "project_id")
    agent_id = _uuid(payload.get("agent_id"))
    trace_id = _required_uuid(payload, "trace_id")
    occurred_at = _occurred_at(payload)
    await SQLAlchemyUsageEventRepository(session).save(
        UsageEvent(
            project_id=project_id,
            agent_id=agent_id,
            source_event_id=_uuid(kwargs.get("source_event_id")),
            occurred_at=occurred_at,
            trace_id=trace_id,
            call_id=str(payload.get("tool_call_id")) if payload.get("tool_call_id") else None,
            environment=payload.get("execution_context") or payload.get("environment"),
            agent_release_id=_uuid(payload.get("agent_release_id")),
            agent_release_version=payload.get("agent_release_version"),
            event_type=UsageEventType.tool_call,
            quantity=1.0,
            unit=UsageUnit.call,
            data=payload,
        )
    )
    await _increment_daily(
        session,
        project_id=project_id,
        agent_id=agent_id,
        day=occurred_at.date(),
        occurred_at=occurred_at,
        tool_calls=1,
    )


async def _handle_terminal_request(
    payload: dict[str, Any],
    session: AsyncSession,
    *,
    source_event_id: UUID | None,
    status: str,
) -> None:
    project_id = _required_uuid(payload, "project_id")
    agent_id = _uuid(payload.get("agent_id"))
    trace_id = _required_uuid(payload, "trace_id")
    occurred_at = _occurred_at(payload)
    cost_status = str(payload.get("cost_status") or "unknown")
    priced, partial, unpriced = _cost_request_deltas(cost_status)
    await SQLAlchemyUsageEventRepository(session).save(
        UsageEvent(
            project_id=project_id,
            agent_id=agent_id,
            source_event_id=source_event_id,
            occurred_at=occurred_at,
            trace_id=trace_id,
            environment=payload.get("execution_context") or payload.get("environment"),
            agent_release_id=_uuid(payload.get("agent_release_id")),
            agent_release_version=payload.get("agent_release_version"),
            provider=payload.get("provider"),
            model=payload.get("model"),
            provider_model_id=_uuid(payload.get("provider_model_id")),
            event_type=UsageEventType.runtime_request,
            quantity=1.0,
            unit=UsageUnit.request,
            input_tokens=_int_or_none(payload.get("input_tokens")),
            output_tokens=_int_or_none(payload.get("output_tokens")),
            cost_usd=_float_or_none(payload.get("cost_usd")),
            cost_status=cost_status,
            cost_reason=payload.get("cost_reason"),
            usage_complete=payload.get("usage_complete"),
            pricing_snapshot=payload.get("pricing_snapshot"),
            data={**payload, "terminal_status": status},
        )
    )
    await _increment_daily(
        session,
        project_id=project_id,
        agent_id=agent_id,
        day=occurred_at.date(),
        occurred_at=occurred_at,
        requests=1,
        successful_requests=1 if status == "completed" else 0,
        failed_requests=1 if status == "failed" else 0,
        cancelled_requests=1 if status == "cancelled" else 0,
        priced_requests=priced,
        partial_cost_requests=partial,
        unpriced_requests=unpriced,
    )


async def handle_execution_completed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        raise RuntimeError("Metering session is required")
    await _handle_terminal_request(
        payload,
        session,
        source_event_id=_uuid(kwargs.get("source_event_id")),
        status="completed",
    )


async def handle_execution_failed(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        raise RuntimeError("Metering session is required")
    terminal_status = "cancelled" if payload.get("status") == "cancelled" else "failed"
    await _handle_terminal_request(
        payload,
        session,
        source_event_id=_uuid(kwargs.get("source_event_id")),
        status=terminal_status,
    )


async def handle_fallback(
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession | None = None,
    **kwargs: Any,
) -> None:
    if session is None:
        raise RuntimeError("Metering session is required")
    project_id = _required_uuid(payload, "project_id")
    occurred_at = _occurred_at(payload)
    await SQLAlchemyUsageEventRepository(session).save(
        UsageEvent(
            project_id=project_id,
            agent_id=_uuid(payload.get("agent_id")),
            source_event_id=_uuid(kwargs.get("source_event_id")),
            occurred_at=occurred_at,
            trace_id=_required_uuid(payload, "trace_id"),
            environment=payload.get("execution_context") or payload.get("environment"),
            event_type=UsageEventType.llm_request,
            quantity=0.0,
            unit=UsageUnit.request,
            cost_status="metadata",
            data={**payload, "source": "fallback_triggered"},
        )
    )


HANDLER_MAP: dict[str, EventHandler] = {
    "agent.execution.requested.v1": handle_noop,
    "agent.execution.started.v1": handle_noop,
    "agent.execution.llm_completed.v1": handle_llm_request,
    "agent.execution.tool_completed.v1": handle_tool_execution,
    "agent.execution.fallback_triggered.v1": handle_fallback,
    "agent.execution.completed.v1": handle_execution_completed,
    "agent.execution.failed.v1": handle_execution_failed,
}


class MeteringInboxEventRouter:
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
            logger.warning("No handler registered for event_type=%s, skipping", event_type)
            return
        await handler(event_type=event_type, payload=payload, **kwargs)

    @property
    def registered_event_types(self) -> list[str]:
        return list(self._handlers.keys())
