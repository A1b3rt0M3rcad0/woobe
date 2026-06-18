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

logger = logging.getLogger(__name__)

_DATA_FIELDS = {
    "message_id",
    "message_preview",
    "answer_length",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "latency_ms",
    "sources",
    "tool_calls",
    "parsed_output",
    "output_parse_error",
    "fallback_used",
    "fallback_info",
    "model",
    "provider",
    "diagnostics",
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


def _rounded(value: float | None) -> int | float | None:
    if value is None:
        return None
    rounded = round(value, 3)
    return int(rounded) if rounded.is_integer() else rounded


def _event_id(trace_id: UUID, discriminator: str) -> UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"projectrai:{trace_id}:{discriminator}")


def _merge_data(trace: Trace, payload: dict[str, Any], event_type: str) -> None:
    data = dict(trace.data or {})
    for field in _DATA_FIELDS:
        if payload.get(field) is not None:
            data[field] = payload[field]
    data["last_event_type"] = event_type
    trace.data = data


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


def _tool_http_latency_ms(tool: dict[str, Any]) -> float | None:
    output = tool.get("output")
    if not isinstance(output, dict):
        return None

    direct = _number(output.get("duration_ms"))
    if direct is not None:
        return direct

    nested = output.get("output")
    if isinstance(nested, dict):
        return _number(nested.get("duration_ms"))
    return None


def _build_execution_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    raw_tools = payload.get("tool_calls")
    tools = [item for item in raw_tools if isinstance(item, dict)] if isinstance(raw_tools, list) else []

    tool_runtime_ms = sum(
        duration
        for tool in tools
        if (duration := _number(tool.get("duration_ms") or tool.get("latency_ms"))) is not None
    )
    tool_http_ms = sum(
        duration
        for tool in tools
        if (duration := _tool_http_latency_ms(tool)) is not None
    )

    runtime_ms = _number(payload.get("total_latency_ms") or payload.get("latency_ms"))
    non_tool_ms = max(runtime_ms - tool_runtime_ms, 0.0) if runtime_ms is not None else None
    tool_overhead_ms = max(tool_runtime_ms - tool_http_ms, 0.0)

    successful_tools = sum(1 for tool in tools if tool.get("success") is True)
    failed_tools = sum(1 for tool in tools if tool.get("success") is False)
    source_count = len(payload.get("sources")) if isinstance(payload.get("sources"), list) else 0

    tool_share = None
    if runtime_ms and runtime_ms > 0:
        tool_share = round((tool_runtime_ms / runtime_ms) * 100, 2)

    return {
        "schema_version": 1,
        "agent_runtime_latency_ms": _rounded(runtime_ms),
        "tool_runtime_latency_ms": _rounded(tool_runtime_ms),
        "tool_http_latency_ms": _rounded(tool_http_ms),
        "tool_overhead_latency_ms": _rounded(tool_overhead_ms),
        "non_tool_runtime_latency_ms": _rounded(non_tool_ms),
        "tool_share_percent": tool_share,
        "tool_call_count": len(tools),
        "successful_tool_calls": successful_tools,
        "failed_tool_calls": failed_tools,
        "input_tokens": payload.get("input_tokens"),
        "output_tokens": payload.get("output_tokens"),
        "total_tokens": payload.get("total_tokens"),
        "source_count": source_count,
        "answer_length": payload.get("answer_length"),
        "fallback_used": bool(payload.get("fallback_used")),
        "structured_output": payload.get("parsed_output") is not None,
        "provider": payload.get("provider"),
        "model": payload.get("model"),
        "notes": [
            "non_tool_runtime_latency_ms includes all model calls and orchestration outside Tool execution",
            "token counters reflect the usage reported by the Agent runtime",
        ],
    }


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
            "Trace projection created trace_id=%s project_id=%s session_id=%s",
            trace_id,
            project_id,
            trace.session_id,
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
        trace.total_cost_usd = float(payload.get("cost_usd") or trace.total_cost_usd or 0)
        await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator="llm_completed",
            kind=TraceEventType.llm_call,
            latency_ms=payload.get("latency_ms"),
            cost_usd=payload.get("cost_usd"),
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
        await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=project_id,
            discriminator="failed",
            kind=TraceEventType.error,
            payload={"event": event_type, **payload},
        )
        return

    if event_type != "agent.execution.completed.v1":
        raise ValueError(f"No trace projection for event_type={event_type}")

    diagnostics = _build_execution_diagnostics(payload)
    payload_with_diagnostics = {**payload, "diagnostics": diagnostics}

    trace.status = TraceStatus.completed
    trace.started_at = trace.started_at or datetime.now(timezone.utc)
    trace.ended_at = datetime.now(timezone.utc)
    trace.fallback_used = bool(payload.get("fallback_used") or trace.fallback_used)
    trace.total_cost_usd = float(payload.get("cost_usd") or trace.total_cost_usd or 0)
    trace.total_latency_ms = (
        payload.get("total_latency_ms")
        or payload.get("latency_ms")
        or trace.total_latency_ms
    )
    _merge_data(trace, payload_with_diagnostics, event_type)
    await trace_repo.save(trace)

    tool_calls = payload.get("tool_calls")
    if isinstance(tool_calls, list):
        for index, raw in enumerate(tool_calls):
            tool = raw if isinstance(raw, dict) else {}
            discriminator = _tool_discriminator(tool, str(index))
            await _save_event(
                event_repo,
                trace_id=trace_id,
                project_id=project_id,
                discriminator=f"tool_completed:{discriminator}",
                kind=TraceEventType.tool_call,
                latency_ms=tool.get("duration_ms") or tool.get("latency_ms"),
                payload={
                    "event": "agent.execution.tool_completed.v1",
                    "trace_id": str(trace_id),
                    **tool,
                },
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
        "Trace projection completed trace_id=%s runtime_ms=%s tool_ms=%s tool_calls=%s",
        trace_id,
        diagnostics["agent_runtime_latency_ms"],
        diagnostics["tool_runtime_latency_ms"],
        diagnostics["tool_call_count"],
    )
