from uuid import uuid4

import pytest

from modules.observability.domain.entities import Trace
from modules.observability.domain.enums import TraceStatus
from modules.observability.infra.messaging import trace_projector


@pytest.mark.asyncio
async def test_completed_snapshot_tool_event_contains_trace_id(monkeypatch) -> None:
    trace_id = uuid4()
    project_id = uuid4()
    trace = Trace(
        id=trace_id,
        project_id=project_id,
        status=TraceStatus.running,
        data={},
    )
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
        session=object(),
    )

    tool_event = saved_events[1]
    assert tool_event.payload["trace_id"] == str(trace_id)
