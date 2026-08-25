from __future__ import annotations

from uuid import uuid4

import pytest

from modules.observability.application.dtos.observability_dtos import TraceEventResponse
from modules.observability.domain.entities import Trace
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.infra.messaging import trace_projector


def test_trace_event_response_derives_trace_id_from_payload() -> None:
    trace_id = uuid4()
    response = TraceEventResponse(
        id=uuid4(),
        event_type="tool_call",
        payload={"trace_id": str(trace_id)},
    )
    assert response.trace_id == trace_id


@pytest.mark.asyncio
async def test_incomplete_direct_tool_event_is_deferred(monkeypatch) -> None:
    trace_id = uuid4()
    trace = Trace(id=trace_id, project_id=uuid4(), status=TraceStatus.running, data={})
    saved_events = []

    class TraceRepo:
        async def get_by_id(self, _trace_id):
            return trace

        async def save(self, value):
            return value

    class EventRepo:
        async def save(self, value):
            saved_events.append(value)
            return value

    monkeypatch.setattr(trace_projector, "SQLAlchemyTraceRepository", lambda _session: TraceRepo())
    monkeypatch.setattr(trace_projector, "SQLAlchemyTraceEventRepository", lambda _session: EventRepo())

    await trace_projector.project_agent_event(
        event_type="agent.execution.tool_completed.v1",
        payload={
            "trace_id": str(trace_id),
            "tool_name": "sum_two_numbers",
            "duration_ms": 100,
            "success": True,
        },
        session=object(),
    )
    assert saved_events == []


@pytest.mark.asyncio
async def test_completed_snapshot_preserves_tool_summary_and_terminal_events(monkeypatch) -> None:
    trace_id = uuid4()
    project_id = uuid4()
    trace = Trace(id=trace_id, project_id=project_id, status=TraceStatus.running, data={})
    saved_events = []

    class TraceRepo:
        async def get_by_id(self, _trace_id):
            return trace

        async def save(self, value):
            return value

    class EventRepo:
        async def get_by_id(self, _event_id):
            return None

        async def save(self, value):
            saved_events.append(value)
            return value

    monkeypatch.setattr(trace_projector, "SQLAlchemyTraceRepository", lambda _session: TraceRepo())
    monkeypatch.setattr(trace_projector, "SQLAlchemyTraceEventRepository", lambda _session: EventRepo())

    await trace_projector.project_agent_event(
        event_type="agent.execution.completed.v1",
        payload={
            "trace_id": str(trace_id),
            "project_id": str(project_id),
            "latency_ms": 500,
            "input_tokens": 10,
            "output_tokens": 2,
            "total_tokens": 12,
            "tool_calls": [
                {
                    "tool_call_id": "call-1",
                    "tool_name": "sum_two_numbers",
                    "input": {"a": "1", "b": "2"},
                    "output": {"result": "3"},
                    "duration_ms": 20,
                    "success": True,
                    "error": None,
                }
            ],
        },
        session=object(),
    )

    assert [event.event_type for event in saved_events] == [
        TraceEventType.tool_call,
        TraceEventType.info,
        TraceEventType.info,
    ]
    tool_event, summary_event, completed_event = saved_events
    assert tool_event.payload["tool_call_id"] == "call-1"
    assert tool_event.payload["input"] == {"a": "1", "b": "2"}
    assert tool_event.payload["output"] == {"result": "3"}
    assert summary_event.payload["event"] == "observability.execution.summary.v1"
    assert completed_event.payload["event"] == "agent.execution.completed.v1"