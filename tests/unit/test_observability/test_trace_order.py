from uuid import uuid4

from modules.observability.application.dtos.observability_dtos import TraceEventResponse, TraceSummaryResponse


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
