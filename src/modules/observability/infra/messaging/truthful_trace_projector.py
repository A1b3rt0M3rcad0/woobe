from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.domain.enums import TraceEventType
from modules.observability.infra.database.repositories import (
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.observability.infra.messaging.diagnostics_v2 import build
from modules.observability.infra.messaging.trace_projector import (
    _event_id,
    _save_event,
    _uuid,
    project_agent_event as legacy_project,
)


async def project_agent_event(
    *, event_type: str, payload: dict[str, Any], session: AsyncSession
) -> None:
    await legacy_project(event_type=event_type, payload=payload, session=session)
    trace_id = _uuid(payload.get("trace_id") or payload.get("execution_id"))
    if trace_id is None:
        return
    trace_repo = SQLAlchemyTraceRepository(session)
    event_repo = SQLAlchemyTraceEventRepository(session)
    trace = await trace_repo.get_by_id(trace_id)
    if trace is None:
        return

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
        return

    diagnostics = build(payload)
    data = dict(trace.data or {})
    for field in (
        "message_id", "answer_length", "input_tokens", "output_tokens",
        "total_tokens", "sources", "tool_calls", "llm_calls",
        "parsed_output", "output_parse_error", "fallback_used",
        "fallback_info", "model", "provider", "cost_status",
        "usage_complete",
    ):
        data[field] = payload.get(field)
    data["cost_usd"] = payload.get("cost_usd")
    data["diagnostics"] = diagnostics
    trace.data = data
    trace.total_cost_usd = (
        payload.get("cost_usd")
        if payload.get("cost_status") == "known"
        else None
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
        payload={"event": event_type, **payload, "diagnostics": diagnostics},
    )
