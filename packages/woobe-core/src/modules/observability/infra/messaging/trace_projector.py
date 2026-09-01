from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.infra.database.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.observability.infra.messaging.diagnostics_v2 import (
    build as build_execution_diagnostics,
)

logger = logging.getLogger(__name__)

_DATA_FIELDS = {
    "message_id",
    "message_preview",
    "answer_length",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "cost_status",
    "cost_reason",
    "pricing_id",
    "pricing_snapshot",
    "latency_ms",
    "sources",
    "tool_calls",
    "parsed_output",
    "output_parse_error",
    "fallback_used",
    "fallback_info",
    "model",
    "provider",
    "provider_model_id",
    "provider_credential_id",
    "fallback_provider_model_id",
    "fallback_credential_id",
    "model_binding",
    "fallback_model_binding",
    "diagnostics",
    "llm_calls",
}


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _event_id(trace_id: UUID, discriminator: str) -> UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"projectrai:{trace_id}:{discriminator}")


def _merge_data(trace: Trace, payload: dict[str, Any], event_type: str) -> None:
    data = dict(trace.data or {})
    for field in _DATA_FIELDS:
        if payload.get(field) is not None:
            data[field] = payload[field]
    data["last_event_type"] = event_type
    trace.data = data


def _apply_provider_model_refs(trace: Trace, payload: dict[str, Any]) -> None:
    trace.provider_model_id = (
        _uuid(payload.get("provider_model_id")) or trace.provider_model_id
    )
    trace.provider_credential_id = (
        _uuid(payload.get("provider_credential_id")) or trace.provider_credential_id
    )
    trace.fallback_provider_model_id = (
        _uuid(payload.get("fallback_provider_model_id"))
        or trace.fallback_provider_model_id
    )
    trace.fallback_credential_id = (
        _uuid(payload.get("fallback_credential_id")) or trace.fallback_credential_id
    )


def _apply_cost(trace: Trace, payload: dict[str, Any]) -> None:
    cost = _number(payload.get("cost_usd"))
    if cost is not None:
        trace.total_cost_usd = cost


async def _save_event(
    repo: SQLAlchemyTraceEventRepository,
    *,
    trace_id: UUID,
    project_id: UUID,
    discriminator: str,
    kind: TraceEventType,
    payload: dict[str, Any],
    latency_ms: float | int | None = None,
    cost_usd: float | None = None,
) -> None:
    await repo.save(
        TraceEvent(
            id=_event_id(trace_id, discriminator),
            trace_id=trace_id,
            project_id=project_id,
            event_type=kind,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            payload=payload,
        )
    )


async def _save_tool_snapshot_if_missing(
    repo: SQLAlchemyTraceEventRepository,
    *,
    trace_id: UUID,
    project_id: UUID,
    discriminator: str,
    tool: dict[str, Any],
) -> None:
    """Use completed Run snapshots only as fallback, never as a destructive update."""

    event_discriminator = f"tool_completed:{discriminator}"
    event_id = _event_id(trace_id, event_discriminator)
    if await repo.get_by_id(event_id) is not None:
        return
    await _save_event(
        repo,
        trace_id=trace_id,
        project_id=project_id,
        discriminator=event_discriminator,
        kind=TraceEventType.tool_call,
        latency_ms=tool.get("duration_ms") or tool.get("latency_ms"),
        payload={
            "event": "agent.execution.tool_completed.v1",
            "trace_id": str(trace_id),
            **tool,
        },
    )


def _tool_discriminator(tool: dict[str, Any], fallback: str) -> str:
    return str(
        tool.get("tool_call_id")
        or tool.get("tool_id")
        or tool.get("tool_name")
        or fallback
    )


def _is_complete_tool_payload(payload: dict[str, Any]) -> bool:
    return (
        payload.get("tool_call_id") is not None
        and "input" in payload
        and "output" in payload
    )


def _diagnostics_source(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("diagnostics")
    if isinstance(nested, dict):
        return {**payload, **nested}
    return payload


async def project_agent_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    session: AsyncSession,
) -> None:
    trace_id = _uuid(payload.get("trace_id") or payload.get("execution_id"))
    if trace_id is None:
        raise ValueError(f"{event_type} requires trace_id")

    trace_repo = SQLAlchemyTraceRepository(session)
    event_repo = SQLAlchemyTraceEventRepository(session)
    trace = await trace_repo.get_by_id(trace_id)
    project_id = _uuid(payload.get("project_id"))

    if trace is None:
        if project_id is None:
            raise RuntimeError(
                f"Trace context is not available yet for {event_type} trace_id={trace_id}"
            )
        trace = Trace(
            id=trace_id,
            project_id=project_id,
            agent_id=_uuid(payload.get("agent_id")),
            session_id=_uuid(payload.get("session_id")),
            status=TraceStatus.pending,
            data={},
        )
    else:
        project_id = trace.project_id

    trace.agent_id = trace.agent_id or _uuid(payload.get("agent_id"))
    trace.session_id = trace.session_id or _uuid(payload.get("session_id"))
    trace.provider = payload.get("provider") or trace.provider
    trace.model = payload.get("model") or trace.model
    _apply_provider_model_refs(trace, payload)
    _merge_data(trace, payload, event_type)

    if event_type == "agent.execution.requested.v1":
        await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator="requested",
            kind=TraceEventType.info,
            payload={"event": event_type, **payload},
        )
        logger.info(
            "Trace projection created trace_id=%s project_id=%s session_id=%s provider_model_id=%s",
            trace_id,
            project_id,
            trace.session_id,
            trace.provider_model_id,
        )
        return

    if event_type == "agent.execution.started.v1":
        trace.status = TraceStatus.running
        trace.started_at = trace.started_at or datetime.now(timezone.utc)
        await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator="started",
            kind=TraceEventType.info,
            payload={"event": event_type, **payload},
        )
        return

    if event_type == "agent.execution.llm_completed.v1":
        _apply_cost(trace, payload)
        await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator=f"llm_completed:{payload.get('call_id') or 'latest'}",
            kind=TraceEventType.llm_call,
            latency_ms=payload.get("latency_ms"),
            cost_usd=_number(payload.get("cost_usd")),
            payload={"event": event_type, **payload},
        )
        return

    if event_type == "agent.execution.tool_completed.v1":
        await trace_repo.save(trace)
        if not _is_complete_tool_payload(payload):
            logger.debug(
                "Deferring incomplete tool timeline event until completed snapshot: trace_id=%s tool=%s",
                trace_id,
                payload.get("tool_name"),
            )
            return
        discriminator = _tool_discriminator(payload, "tool")
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator=f"tool_completed:{discriminator}",
            kind=TraceEventType.tool_call,
            latency_ms=payload.get("duration_ms") or payload.get("latency_ms"),
            payload={"event": event_type, **payload},
        )
        return

    if event_type == "agent.execution.fallback_triggered.v1":
        trace.fallback_used = True
        _merge_data(trace, {**payload, "fallback_used": True}, event_type)
        _apply_provider_model_refs(trace, payload)
        await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator="fallback",
            kind=TraceEventType.warning,
            payload={"event": event_type, **payload},
        )
        return

    if event_type == "agent.execution.failed.v1":
        trace.status = TraceStatus.failed
        trace.started_at = trace.started_at or datetime.now(timezone.utc)
        trace.ended_at = datetime.now(timezone.utc)
        trace.error = str(payload.get("error") or "unknown error")
        diagnostics = build_execution_diagnostics(_diagnostics_source(payload))
        payload_with_diagnostics = {**payload, "diagnostics": diagnostics}
        _merge_data(trace, payload_with_diagnostics, event_type)
        await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator="failed",
            kind=TraceEventType.error,
            payload={"event": event_type, **payload_with_diagnostics},
        )
        return

    if event_type != "agent.execution.completed.v1":
        raise ValueError(f"No trace projection for event_type={event_type}")

    diagnostics = build_execution_diagnostics(_diagnostics_source(payload))
    payload_with_diagnostics = {**payload, "diagnostics": diagnostics}

    trace.status = TraceStatus.completed
    trace.started_at = trace.started_at or datetime.now(timezone.utc)
    trace.ended_at = datetime.now(timezone.utc)
    trace.fallback_used = bool(payload.get("fallback_used") or trace.fallback_used)
    _apply_cost(trace, payload)
    trace.total_latency_ms = (
        payload.get("agent_runtime_latency_ms")
        or payload.get("total_latency_ms")
        or payload.get("latency_ms")
        or trace.total_latency_ms
    )
    _apply_provider_model_refs(trace, payload)
    _merge_data(trace, payload_with_diagnostics, event_type)
    await trace_repo.save(trace)

    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, list):
        for index, raw in enumerate(tool_calls):
            tool = raw if isinstance(raw, dict) else {}
            discriminator = _tool_discriminator(tool, str(index))
            await _save_tool_snapshot_if_missing(
                event_repo,
                trace_id=trace_id,
                project_id=project_id,
                discriminator=discriminator,
                tool=tool,
            )

    await _save_event(
        event_repo,
        trace_id=trace_id,
        project_id=project_id,
        discriminator="execution_summary",
        kind=TraceEventType.info,
        latency_ms=trace.total_latency_ms,
        cost_usd=trace.total_cost_usd,
        payload={
            "event": "observability.execution.summary.v1",
            "trace_id": str(trace_id),
            **diagnostics,
        },
    )

    await _save_event(
        event_repo,
        trace_id=trace_id,
        project_id=project_id,
        discriminator="completed",
        kind=TraceEventType.info,
        latency_ms=trace.total_latency_ms,
        cost_usd=trace.total_cost_usd,
        payload={"event": event_type, **payload_with_diagnostics},
    )

    logger.info(
        "Trace projection completed trace_id=%s runtime_ms=%s tool_wall_ms=%s tool_work_ms=%s tool_calls=%s provider_model_id=%s cost_status=%s",
        trace_id,
        diagnostics["agent_runtime_latency_ms"],
        diagnostics["tool_wall_latency_ms"],
        diagnostics["tool_work_latency_ms"],
        diagnostics["tool_call_count"],
        trace.provider_model_id,
        diagnostics["cost_status"],
    )
