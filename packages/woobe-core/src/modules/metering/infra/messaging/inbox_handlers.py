from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.metering.infra.messaging.daily_usage import _increment_daily
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


async def handle_artifact_model_usage(event_type, payload, session=None, **kwargs):
    from modules.metering.infra.messaging.document_model_usage import handle_document_model_usage
    await handle_document_model_usage(event_type, payload, session=session, **kwargs)


HANDLER_MAP: dict[str, EventHandler] = {
    "artifact.processing.model_usage.v1": handle_artifact_model_usage,
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
