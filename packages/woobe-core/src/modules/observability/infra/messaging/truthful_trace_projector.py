from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from modules.observability.domain.entities import Trace
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.infra.database.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from modules.observability.infra.messaging.diagnostics_v2 import build
from modules.observability.infra.messaging.trace_projector import (
    _event_id,
    _save_event,
    _uuid,
    project_agent_event as legacy_project,
)

_RUNTIME_DIMENSION_FIELDS = (
    "execution_context",
    "agent_release_id",
    "agent_release_version",
    "provider_model_id",
    "provider_credential_id",
    "fallback_provider_model_id",
    "fallback_credential_id",
)

_COMPLETION_EVENT_FIELDS = (
    "trace_id",
    "project_id",
    "agent_id",
    "session_id",
    "message_id",
    "answer_length",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "cost_status",
    "cost_reason",
    "usage_complete",
    "model",
    "provider",
    "latency_ms",
    "total_latency_ms",
    "fallback_used",
    "llm_call_count",
    "tool_call_count",
    "source_count",
    "failed_tool_calls",
    "successful_tool_calls",
    "structured_output",
    "execution_context",
    "agent_release_id",
    "agent_release_version",
    "provider_model_id",
    "provider_credential_id",
    "fallback_provider_model_id",
    "fallback_credential_id",
)


def _completion_event_payload(
    payload: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    compact = {
        field: payload.get(field, diagnostics.get(field))
        for field in _COMPLETION_EVENT_FIELDS
    }
    return {
        "event": "agent.execution.completed.v1",
        **compact,
        "diagnostics": diagnostics,
    }


def _apply_provider_model_refs(trace: Trace, payload: dict[str, Any]) -> None:
    trace.provider_model_id = _uuid(payload.get("provider_model_id")) or trace.provider_model_id
    trace.provider_credential_id = _uuid(payload.get("provider_credential_id")) or trace.provider_credential_id
    trace.fallback_provider_model_id = _uuid(payload.get("fallback_provider_model_id")) or trace.fallback_provider_model_id
    trace.fallback_credential_id = _uuid(payload.get("fallback_credential_id")) or trace.fallback_credential_id


def _apply_runtime_dimensions(trace: Trace, payload: dict[str, Any]) -> None:
    data = dict(trace.data or {})
    diagnostics = payload.get("diagnostics")
    diagnostic_values = diagnostics if isinstance(diagnostics, dict) else {}
    for field in _RUNTIME_DIMENSION_FIELDS:
        value = payload.get(field)
        if value is None:
            value = diagnostic_values.get(field)
        if value is not None:
            data[field] = value
    for field in ("llm_call_count", "tool_call_count"):
        value = payload.get(field)
        if value is None:
            value = diagnostic_values.get(field)
        if value is not None:
            data[field] = value
    trace.data = data


async def _project_cancelled(
    *,
    payload: dict[str, Any],
    uow: ObservabilityUnitOfWork,
) -> None:
    trace_id = _uuid(payload.get("trace_id") or payload.get("execution_id"))
    project_id = _uuid(payload.get("project_id"))
    if trace_id is None:
        return
    trace_repo = SQLAlchemyTraceRepository(uow)
    event_repo = SQLAlchemyTraceEventRepository(uow)
    trace = await trace_repo.get_by_id(trace_id)
    if trace is None:
        if project_id is None:
            return
        trace = Trace(
            id=trace_id,
            project_id=project_id,
            agent_id=_uuid(payload.get("agent_id")),
            session_id=_uuid(payload.get("session_id")),
            status=TraceStatus.cancelled,
            data={},
        )
    now = datetime.now(timezone.utc)
    trace.status = TraceStatus.cancelled
    trace.started_at = trace.started_at or now
    trace.ended_at = now
    _apply_provider_model_refs(trace, payload)
    _apply_runtime_dimensions(trace, payload)
    data = dict(trace.data or {})
    data.update(
        {
            "last_event_type": "agent.execution.cancelled.v1",
            "cancellation_reason": payload.get("reason"),
            "request_id": payload.get("request_id"),
            "provider_model_id": payload.get("provider_model_id"),
            "provider_credential_id": payload.get("provider_credential_id"),
            "fallback_provider_model_id": payload.get("fallback_provider_model_id"),
            "fallback_credential_id": payload.get("fallback_credential_id"),
        }
    )
    trace.data = data
    await trace_repo.save(trace)
    await _save_event(
        event_repo,
        trace_id=trace_id,
        project_id=trace.project_id,
        discriminator="cancelled",
        kind=TraceEventType.warning,
        payload={"event": "agent.execution.cancelled.v1", **payload},
    )


async def project_agent_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    uow: ObservabilityUnitOfWork,
) -> None:
    if event_type == "agent.execution.cancelled.v1":
        await _project_cancelled(payload=payload, uow=uow)
        return
    await legacy_project(event_type=event_type, payload=payload, uow=uow)
    trace_id = _uuid(payload.get("trace_id") or payload.get("execution_id"))
    if trace_id is None:
        return
    trace_repo = SQLAlchemyTraceRepository(uow)
    event_repo = SQLAlchemyTraceEventRepository(uow)
    trace = await trace_repo.get_by_id(trace_id)
    if trace is None:
        return
    _apply_provider_model_refs(trace, payload)
    _apply_runtime_dimensions(trace, payload)

    if event_type == "agent.execution.llm_completed.v1":
        await event_repo.delete(_event_id(trace_id, "llm_completed"))
        discriminator = payload.get("call_id") or payload.get("call_index") or "call"
        known_cost = payload.get("cost_status") == "known"
        if not known_cost:
            trace.total_cost_usd = None
            await trace_repo.save(trace)
        await _save_event(
            event_repo,
            trace_id=trace_id,
            project_id=trace.project_id,
            discriminator=f"llm_completed:{discriminator}",
            kind=TraceEventType.llm_call,
            latency_ms=payload.get("latency_ms"),
            cost_usd=payload.get("cost_usd") if known_cost else None,
            payload={"event": event_type, **payload},
        )
        return

    if event_type != "agent.execution.completed.v1":
        await trace_repo.save(trace)
        return

    diagnostics = build(payload)
    data = dict(trace.data or {})
    for field in (
        "message_id",
        "answer_length",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "sources",
        "tool_calls",
        "llm_calls",
        "parsed_output",
        "output_parse_error",
        "fallback_used",
        "fallback_info",
        "model",
        "provider",
        "cost_status",
        "cost_reason",
        "pricing_id",
        "pricing_snapshot",
        "usage_complete",
        "execution_events",
        "timeline_complete",
        "provider_model_id",
        "provider_credential_id",
        "fallback_provider_model_id",
        "fallback_credential_id",
        "model_binding",
        "fallback_model_binding",
        "execution_context",
        "agent_release_id",
        "agent_release_version",
        "llm_call_count",
        "tool_call_count",
    ):
        value = payload.get(field)
        if value is None and field in diagnostics:
            value = diagnostics.get(field)
        data[field] = value
    data["cost_usd"] = payload.get("cost_usd")
    data["diagnostics"] = diagnostics
    trace.data = data
    trace.total_cost_usd = (
        payload.get("cost_usd") if payload.get("cost_status") == "known" else None
    )
    trace.total_latency_ms = payload.get("total_latency_ms") or payload.get("latency_ms")
    await trace_repo.save(trace)
    await _save_event(
        event_repo,
        trace_id=trace_id,
        project_id=trace.project_id,
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
        project_id=trace.project_id,
        discriminator="completed",
        kind=TraceEventType.info,
        latency_ms=trace.total_latency_ms,
        cost_usd=trace.total_cost_usd,
        payload=_completion_event_payload(payload, diagnostics),
    )
