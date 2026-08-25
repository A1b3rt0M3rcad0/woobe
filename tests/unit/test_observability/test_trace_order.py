from datetime import datetime, timezone
from uuid import uuid4

from modules.observability.application.dtos.observability_dtos import (
    TraceEventResponse,
    TraceSummaryResponse,
)


def test_trace_event_lifecycle_order() -> None:
    names = [
        "agent.execution.completed.v1",
        "agent.execution.tool_completed.v1",
        "agent.execution.started.v1",
        "agent.execution.llm_completed.v1",
        "agent.execution.requested.v1",
    ]
    events = [
        TraceEventResponse(
            id=uuid4(),
            event_type="info",
            payload={"event": name, "trace_id": str(uuid4())},
        )
        for name in names
    ]
    response = TraceSummaryResponse(
        id=uuid4(),
        project_id=uuid4(),
        status="completed",
        events=events,
    )
    assert [event.payload["event"] for event in response.events] == [
        "agent.execution.requested.v1",
        "agent.execution.started.v1",
        "agent.execution.llm_completed.v1",
        "agent.execution.tool_completed.v1",
        "agent.execution.completed.v1",
    ]


def test_trace_operations_order_by_occurred_at_not_persistence_time() -> None:
    trace_id = uuid4()
    recorded_at = datetime(2026, 8, 25, 2, 13, 30, tzinfo=timezone.utc)
    events = [
        TraceEventResponse(
            id=uuid4(),
            trace_id=trace_id,
            event_type="llm_call",
            created_at=recorded_at,
            payload={
                "event": "agent.execution.llm_completed.v1",
                "call_id": "llm-final",
                "occurred_at": "2026-08-25T02:13:27+00:00",
            },
        ),
        TraceEventResponse(
            id=uuid4(),
            trace_id=trace_id,
            event_type="tool_call",
            created_at=recorded_at,
            payload={
                "event": "agent.execution.tool_completed.v1",
                "tool_call_id": "tool-before-final",
                "occurred_at": "2026-08-25T02:13:17+00:00",
            },
        ),
    ]

    response = TraceSummaryResponse(
        id=trace_id,
        project_id=uuid4(),
        status="completed",
        events=events,
    )

    assert [event.payload["event"] for event in response.events] == [
        "agent.execution.tool_completed.v1",
        "agent.execution.llm_completed.v1",
    ]


def test_trace_operations_use_causal_sequence_to_break_timestamp_ties() -> None:
    trace_id = uuid4()
    occurred_at = "2026-08-25T02:13:17+00:00"
    events = [
        TraceEventResponse(
            id=uuid4(),
            trace_id=trace_id,
            event_type="tool_call",
            payload={
                "event": "agent.execution.tool_completed.v1",
                "tool_call_id": "second",
                "occurred_at": occurred_at,
                "causal_sequence": 2,
            },
        ),
        TraceEventResponse(
            id=uuid4(),
            trace_id=trace_id,
            event_type="tool_call",
            payload={
                "event": "agent.execution.tool_completed.v1",
                "tool_call_id": "first",
                "occurred_at": occurred_at,
                "causal_sequence": 1,
            },
        ),
    ]

    response = TraceSummaryResponse(
        id=trace_id,
        project_id=uuid4(),
        status="completed",
        events=events,
    )

    assert [event.payload["tool_call_id"] for event in response.events] == [
        "first",
        "second",
    ]
