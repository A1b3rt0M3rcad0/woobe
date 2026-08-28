from types import SimpleNamespace
from uuid import uuid4

from shared.runtime_reattach import (
    _public_event,
    initial_projection,
    reduce_projection,
)


def test_projection_separates_delegations_from_operational_tools() -> None:
    state = initial_projection(uuid4(), "network")

    delegation_started = SimpleNamespace(
        event_type="tool_call_started",
        payload={
            "tool_call_id": "delegate-call",
            "tool_name": "delegate_to_support",
            "invocation_id": "root",
            "input": {"task": "help"},
        },
    )
    public_type, public_payload = _public_event(delegation_started)
    assert public_type == "run.progress"
    assert public_payload == {}

    state = reduce_projection(
        state,
        "delegation_started",
        {
            "invocation_id": "root",
            "target_node_id": "support",
            "target": "Support Agent",
            "task_fingerprint": "root:support",
        },
        sequence=1,
        occurred_at="2026-08-27T12:00:00+00:00",
    )

    assert state["tools"] == []
    assert state["delegations"] == [
        {
            "id": "root:support",
            "parent_invocation_id": "root",
            "target_node_id": "support",
            "target": "Support Agent",
            "status": "running",
            "reason": None,
            "started_at": "2026-08-27T12:00:00+00:00",
            "completed_at": None,
        }
    ]


def test_projection_preserves_safe_operational_tool_summary() -> None:
    state = initial_projection(uuid4(), "network")
    started_event = SimpleNamespace(
        event_type="tool_call_started",
        payload={
            "tool_call_id": "tool-1",
            "tool_name": "lookup_customer",
            "invocation_id": "root",
            "input": {"customer_id": "secret-ish-input"},
            "authorization": "Bearer secret",
            "started_at": "2026-08-27T12:00:00+00:00",
        },
    )
    event_type, payload = _public_event(started_event)
    assert event_type == "tool_call_started"
    assert "input" not in payload
    assert "authorization" not in payload
    state = reduce_projection(
        state,
        event_type,
        payload,
        sequence=1,
        occurred_at="2026-08-27T12:00:00+00:00",
    )

    completed_event = SimpleNamespace(
        event_type="tool_call_completed",
        payload={
            "tool_call_id": "tool-1",
            "tool_name": "lookup_customer",
            "invocation_id": "root",
            "output": {"email": "private@example.com"},
            "duration_ms": 120,
            "success": True,
            "status": "success",
            "ended_at": "2026-08-27T12:00:00.120000+00:00",
        },
    )
    event_type, payload = _public_event(completed_event)
    assert event_type == "tool_call_completed"
    assert "output" not in payload
    state = reduce_projection(
        state,
        event_type,
        payload,
        sequence=2,
        occurred_at="2026-08-27T12:00:00.120000+00:00",
    )

    assert state["active_tools"] == []
    assert state["tools"] == [
        {
            "id": "tool-1",
            "tool_call_id": "tool-1",
            "invocation_id": "root",
            "tool_name": "lookup_customer",
            "status": "success",
            "success": True,
            "started_at": "2026-08-27T12:00:00+00:00",
            "duration_ms": 120,
            "error_code": None,
            "error": None,
            "completed_at": "2026-08-27T12:00:00.120000+00:00",
        }
    ]
