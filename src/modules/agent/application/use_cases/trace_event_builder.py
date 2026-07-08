from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


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
        elif item.get("kind") == "rag":
            occurred_at = str(ended_at or started_at or "")
            attributes = {
                key: value
                for key, value in payload.items()
                if key not in {"started_at", "ended_at", "occurred_at"}
            }
            events.append(_event(
                trace_id,
                "rag.retrieval.completed",
                occurred_at,
                phase="retrieval",
                status="success",
                started_at=started_at,
                ended_at=ended_at,
                duration_ms=None,
                attributes=attributes,
            ))
    events.sort(key=lambda event: (_ts(event.get("occurred_at")), event.get("event_type", "")))
    return events


def sequence_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events.sort(key=lambda event: (_ts(event.get("occurred_at")), event.get("event_type", "")))
    for index, event in enumerate(events, start=1):
        event["sequence"] = index
    return events
