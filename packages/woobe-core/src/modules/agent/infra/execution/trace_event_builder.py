from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


_EVENT_ORDER = {
    "http.request.received": 10,
    "agent.execution.started": 20,
    "agent.prepare.started": 30,
    "agent.prepare.completed": 40,
    "llm.call.started": 50,
    "tool.call.started": 50,
    "rag.retrieval.completed": 55,
    "knowledge.retrieval.completed": 55,
    "llm.call.completed": 60,
    "tool.call.completed": 60,
    "structured_output.parse.completed": 70,
    "message.persistence.started": 80,
    "message.persistence.completed": 90,
    "agent.execution.completed": 100,
    "http.response.prepared": 110,
}


def _event_sort_key(event: dict[str, Any]) -> tuple[float, int, str]:
    event_type = str(event.get("event_type") or "")
    return (
        _ts(event.get("occurred_at")),
        _EVENT_ORDER.get(event_type, 65),
        event_type,
    )


def _ts(value: str | None) -> float:
    if not value:
        return float("inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("inf")


def _event(trace_id: str, event_type: str, occurred_at: str, **fields: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event_id": str(uuid4()),
        "trace_id": trace_id,
        "root_span_id": trace_id,
        "span_id": fields.pop("span_id", str(uuid4())),
        "parent_span_id": fields.pop("parent_span_id", trace_id),
        "sequence": 0,
        "event_type": event_type,
        "occurred_at": occurred_at,
        **fields,
    }


def build_operation_events(trace_id: str, timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    previous_llm: dict[str, Any] | None = None
    pending_tools: list[str] = []
    for item in timeline:
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        started_at = payload.get("started_at")
        ended_at = payload.get("ended_at") or payload.get("occurred_at")
        if item.get("kind") == "llm":
            span_id = str(payload.get("call_id") or uuid4())
            common = {
                "call_id": payload.get("call_id"),
                "call_index": payload.get("call_index"),
                "provider": payload.get("provider"),
                "model": payload.get("model"),
                "received_tool_call_ids": list(pending_tools),
            }
            pending_tools.clear()
            if started_at:
                events.append(_event(
                    trace_id, "llm.call.started", str(started_at),
                    span_id=span_id, phase=payload.get("phase"), status="running",
                    started_at=started_at, ended_at=None, duration_ms=None,
                    attributes=dict(common),
                ))
            previous_llm = {
                **common,
                "input_tokens": payload.get("input_tokens"),
                "output_tokens": payload.get("output_tokens"),
                "total_tokens": payload.get("total_tokens"),
                "cost_usd": payload.get("cost_usd"),
                "cost_status": payload.get("cost_status"),
                "usage_complete": payload.get("usage_complete"),
                "error": payload.get("error"),
                "requested_tool_call_ids": [],
            }
            events.append(_event(
                trace_id, "llm.call.completed", str(ended_at),
                span_id=span_id, phase=payload.get("phase"),
                status=payload.get("status") or "success",
                started_at=started_at, ended_at=ended_at,
                duration_ms=payload.get("latency_ms"), attributes=previous_llm,
            ))
        elif item.get("kind") == "tool":
            tool_id = str(payload.get("tool_call_id") or uuid4())
            pending_tools.append(tool_id)
            if previous_llm is not None:
                previous_llm["requested_tool_call_ids"].append(tool_id)
            common = {
                "tool_call_id": tool_id,
                "tool_id": payload.get("tool_id"),
                "tool_name": payload.get("tool_name"),
                "tool_runtime_source": payload.get("tool_runtime_source"),
                "tool_snapshot_hash": payload.get("tool_snapshot_hash"),
                "input": payload.get("input"),
            }
            if started_at:
                events.append(_event(
                    trace_id, "tool.call.started", str(started_at),
                    span_id=tool_id, phase="tool_execution", status="running",
                    started_at=started_at, ended_at=None, duration_ms=None,
                    attributes=common,
                ))
            total = float(payload.get("duration_ms") or 0)
            http = float(payload.get("http_latency_ms") or 0)
            events.append(_event(
                trace_id, "tool.call.completed", str(ended_at),
                span_id=tool_id, phase="tool_execution",
                status=payload.get("status") or "success",
                started_at=started_at, ended_at=ended_at,
                duration_ms=payload.get("duration_ms"),
                attributes={
                    **common,
                    "output": payload.get("output"),
                    "http_duration_ms": payload.get("http_latency_ms"),
                    "overhead_duration_ms": max(total - http, 0),
                    "success": payload.get("success"),
                    "error": payload.get("error"),
                },
            ))
        elif item.get("kind") in {"rag", "knowledge"}:
            occurred_at = str(ended_at or started_at or "")
            attributes = {
                key: value
                for key, value in payload.items()
                if key not in {"started_at", "ended_at", "occurred_at"}
            }
            events.append(_event(
                trace_id,
                (
                    "knowledge.retrieval.completed"
                    if item.get("kind") == "knowledge"
                    else "rag.retrieval.completed"
                ),
                occurred_at,
                phase="retrieval",
                status="success",
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=None,
                attributes=attributes,
            ))
    events.sort(key=_event_sort_key)
    return events


def build_execution_timeline_events(
    trace_id: str,
    *,
    context: Any,
    timeline: list[dict[str, Any]],
    completed_at: str,
    total_latency_ms: int | float | None,
    output_parse_error: str | None,
    completion_attributes: dict[str, Any] | None = None,
    include_http_boundaries: bool = False,
) -> list[dict[str, Any]]:
    """Build the compatibility execution timeline from canonical runtime telemetry.

    The durable journal remains the source of truth. This is a read-model snapshot
    consumed by Observability and the Run inspector so event_journal executions keep
    the same detailed timeline contract as legacy finalization.
    """

    request_received_at = (
        getattr(context, "request_received_at", None) or completed_at
    )
    execution_started_at = (
        getattr(context, "execution_started_at", None) or request_received_at
    )
    events: list[dict[str, Any]] = []

    if include_http_boundaries:
        events.append(
            _event(
                trace_id,
                "http.request.received",
                request_received_at,
                phase="request",
                status="success",
                started_at=request_received_at,
                ended_at=request_received_at,
                duration_ms=0,
                span_id=trace_id,
                parent_span_id=None,
                attributes={
                    "client_sent_at": getattr(context, "client_sent_at", None),
                },
            )
        )

    events.append(
        _event(
            trace_id,
            "agent.execution.started",
            execution_started_at,
            phase="execution",
            status="running",
            started_at=execution_started_at,
            ended_at=None,
            duration_ms=None,
            span_id=trace_id,
            parent_span_id=None,
            attributes={},
        )
    )

    prepare_started_at = getattr(context, "prepare_started_at", None)
    if prepare_started_at:
        prepare_ended_at = (
            getattr(context, "prepare_ended_at", None) or prepare_started_at
        )
        prepare_span = str(uuid4())
        events.extend(
            [
                _event(
                    trace_id,
                    "agent.prepare.started",
                    prepare_started_at,
                    phase="prepare",
                    status="running",
                    started_at=prepare_started_at,
                    ended_at=None,
                    duration_ms=None,
                    span_id=prepare_span,
                ),
                _event(
                    trace_id,
                    "agent.prepare.completed",
                    prepare_ended_at,
                    phase="prepare",
                    status="success",
                    started_at=prepare_started_at,
                    ended_at=prepare_ended_at,
                    duration_ms=getattr(context, "prepare_latency_ms", None),
                    span_id=prepare_span,
                ),
            ]
        )

    events.extend(build_operation_events(trace_id, timeline))
    events.extend(
        [
            _event(
                trace_id,
                "structured_output.parse.completed",
                completed_at,
                phase="structured_output",
                status="success" if output_parse_error is None else "error",
                started_at=None,
                ended_at=completed_at,
                duration_ms=None,
                attributes={
                    "error": output_parse_error,
                    "duration_measured": False,
                },
            ),
            _event(
                trace_id,
                "agent.execution.completed",
                completed_at,
                phase="execution",
                status="success",
                started_at=execution_started_at,
                ended_at=completed_at,
                duration_ms=total_latency_ms,
                span_id=trace_id,
                parent_span_id=None,
                attributes=completion_attributes or {},
            ),
        ]
    )

    if include_http_boundaries:
        events.append(
            _event(
                trace_id,
                "http.response.prepared",
                completed_at,
                phase="response",
                status="success",
                started_at=None,
                ended_at=completed_at,
                duration_ms=None,
                attributes={},
            )
        )

    return sequence_events(events)


def sequence_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events.sort(key=_event_sort_key)
    for index, event in enumerate(events, start=1):
        event["sequence"] = index
    return events
