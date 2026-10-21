from types import SimpleNamespace
from uuid import uuid4

from shared.runtime.projection import initial_projection, public_event, reduce_projection


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
    public_type, public_payload = public_event(delegation_started)
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
    event_type, payload = public_event(started_event)
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
    event_type, payload = public_event(completed_event)
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


def test_artifact_available_replay_is_idempotent_and_schema_stable() -> None:
    run_id = uuid4()
    terminal_artifact = {
        "schema_version": "1",
        "ref": {"artifact_id": "artifact-1", "revision_id": "revision-2"},
        "path": "outputs/result.txt",
        "content_type": "text/plain; charset=utf-8",
        "size_bytes": 4,
        "sha256": "a" * 64,
        "status": "available",
        "run_id": str(run_id),
        "node_id": None,
        "source_refs": [],
    }
    state = initial_projection(run_id, "agent")
    payload = {
        "artifact_id": "artifact-1",
        "revision_id": "revision-2",
        "path": "outputs/result.txt",
        "content_type": "text/plain; charset=utf-8",
        "size_bytes": 4,
        "sha256": "a" * 64,
        "status": "available",
        "run_id": str(run_id),
        "node_id": None,
        "private_blob": "must never appear in the event projection",
    }

    state = reduce_projection(
        state, "artifact_available", payload, sequence=1,
        occurred_at="2026-10-21T00:00:00+00:00",
    )
    state = reduce_projection(
        state, "artifact_available", payload, sequence=1,
        occurred_at="2026-10-21T00:00:00+00:00",
    )
    assert state["output_artifacts"] == [{key: value for key, value in terminal_artifact.items() if key != "source_refs"} | {"source_refs": []}]

    terminal_state = initial_projection(
        run_id,
        "agent",
        {"terminal_result": {"output_artifacts": [terminal_artifact], "source_refs": []}},
    )
    assert terminal_state["output_artifacts"] == state["output_artifacts"]
