from datetime import datetime
from uuid import UUID

from modules.observability.application.dtos.observability_dtos import (
    TraceEventResponse,
    TraceSummaryResponse,
)


TRACE_ID = UUID("00000000-0000-0000-0000-000000000001")
PROJECT_ID = UUID("00000000-0000-0000-0000-000000000002")


def _event(event_id: int, event_type: str, payload: dict, created_at: str):
    return TraceEventResponse(
        id=UUID(f"00000000-0000-0000-0000-{event_id:012d}"),
        trace_id=TRACE_ID,
        event_type=event_type,
        payload=payload,
        created_at=datetime.fromisoformat(created_at),
    )


def test_legacy_tool_events_are_ordered_before_llm_followup_from_canonical_timeline():
    tool_call_id = "call-tool-1"
    planning_call_id = "call-llm-1"
    followup_call_id = "call-llm-2"

    events = [
        _event(
            1,
            "llm_call",
            {
                "event": "agent.execution.llm_completed.v1",
                "call_id": planning_call_id,
                "occurred_at": "2026-06-17T15:18:27.779379+00:00",
            },
            "2026-06-17T15:18:27.779379+00:00",
        ),
        _event(
            2,
            "llm_call",
            {
                "event": "agent.execution.llm_completed.v1",
                "call_id": followup_call_id,
                "occurred_at": "2026-06-17T15:18:29.850741+00:00",
            },
            "2026-06-17T15:18:29.850741+00:00",
        ),
        _event(
            3,
            "tool_call",
            {
                "event": "agent.execution.tool_completed.v1",
                "tool_call_id": tool_call_id,
            },
            "2026-06-17T15:18:30.216983+00:00",
        ),
        _event(
            4,
            "info",
            {
                "event": "agent.execution.completed.v1",
                "execution_events": [
                    {
                        "event_type": "tool.call.completed",
                        "event_id": "00000000-0000-0000-0000-000000000010",
                        "span_id": tool_call_id,
                        "sequence": 9,
                        "started_at": "2026-06-17T15:18:27.779428+00:00",
                        "ended_at": "2026-06-17T15:18:28.515121+00:00",
                        "occurred_at": "2026-06-17T15:18:28.515121+00:00",
                        "duration_ms": 736,
                        "status": "success",
                        "phase": "tool_execution",
                        "attributes": {"tool_call_id": tool_call_id},
                    }
                ],
            },
            "2026-06-17T15:18:30.264500+00:00",
        ),
    ]

    trace = TraceSummaryResponse(
        id=TRACE_ID,
        project_id=PROJECT_ID,
        status="completed",
        events=events,
    )

    operational = [
        event.payload["event"]
        for event in trace.events
        if event.payload["event"] != "agent.execution.completed.v1"
    ]
    assert operational == [
        "agent.execution.llm_completed.v1",
        "agent.execution.tool_completed.v1",
        "agent.execution.llm_completed.v1",
    ]

    tool_event = next(
        event
        for event in trace.events
        if event.payload.get("tool_call_id") == tool_call_id
    )
    assert tool_event.payload["occurred_at"] == "2026-06-17T15:18:28.515121+00:00"
    assert tool_event.payload["causal_sequence"] == 9
