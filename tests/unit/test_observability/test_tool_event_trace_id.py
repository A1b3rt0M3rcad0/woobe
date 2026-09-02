from uuid import uuid4

import pytest

from modules.observability.domain.entities import Trace
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.infra.messaging import trace_projector


@pytest.mark.asyncio
async def test_completed_snapshot_persists_tool_summary_and_completed(monkeypatch) -> None:
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

    monkeypatch.setattr(trace_projector, "SQLAlchemyTraceRepository", lambda _uow: TraceRepo())
    monkeypatch.setattr(trace_projector, "SQLAlchemyTraceEventRepository", lambda _uow: EventRepo())

    await trace_projector.project_agent_event(
        event_type="agent.execution.completed.v1",
        payload={
            "trace_id": str(trace_id),
            "project_id": str(project_id),
            "tool_calls": [
                {
                    "tool_call_id": "call-1",
                    "tool_name": "sum_two_numbers",
                    "input": {"a": "7", "b": "8"},
                    "output": {"result": "15"},
                    "duration_ms": 20,
                    "success": True,
                }
            ],
        },
        uow=object(),
    )

    assert [event.event_type for event in saved_events] == [
        TraceEventType.tool_call,
        TraceEventType.info,
        TraceEventType.info,
    ]
    tool_event, summary_event, completed_event = saved_events
    assert tool_event.payload["trace_id"] == str(trace_id)
    assert tool_event.payload["event"] == "agent.execution.tool_completed.v1"
    assert summary_event.payload["event"] == "observability.execution.summary.v1"
    assert completed_event.payload["event"] == "agent.execution.completed.v1"
