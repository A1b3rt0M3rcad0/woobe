from uuid import uuid4

import pytest

from modules.observability.domain.entities import Trace
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.infra.messaging import trace_projector


@pytest.mark.asyncio
async def test_completed_event_persists_truthful_execution_diagnostics(monkeypatch) -> None:
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
            "latency_ms": 5000,
            "input_tokens": 500,
            "output_tokens": 50,
            "total_tokens": 550,
            "answer_length": 120,
            "sources": [{"document_id": str(uuid4())}],
            "tool_calls": [{
                "tool_call_id": "call-1",
                "tool_name": "sum_two_numbers",
                "duration_ms": 600,
                "success": True,
                "input": {"a": "1", "b": "2"},
                "output": {
                    "success": True,
                    "provider_latency_ms": 400,
                    "duration_ms": 10,
                    "output": {"result": "3"},
                },
            }],
        },
        uow=object(),
    )
    diagnostics = trace.data["diagnostics"]
    assert diagnostics["schema_version"] == 5
    assert diagnostics["agent_runtime_latency_ms"] == 5000
    assert diagnostics["tool_wall_latency_ms"] == 600
    assert diagnostics["tool_work_latency_ms"] == 600
    assert diagnostics["tool_provider_work_ms"] == 400
    assert diagnostics["tool_runtime_overhead_ms"] == 200
    assert diagnostics["other_latency_ms"] == 4400
    assert diagnostics["tool_share_percent"] == 12.0
    assert diagnostics["tool_call_count"] == 1
    assert diagnostics["source_count"] == 1
    assert [event.event_type for event in saved_events] == [
        TraceEventType.tool_call,
        TraceEventType.info,
        TraceEventType.info,
    ]
