from __future__ import annotations

from uuid import uuid4

import pytest

from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime_reattach import RuntimeEventPublisher, RuntimeStreamReader


@pytest.mark.asyncio
async def test_network_reattach_projection_restores_invocation_tree_without_raw_outputs() -> None:
    store = InMemoryExecutionStateStore()
    publisher = RuntimeEventPublisher(store, projection_interval_seconds=0)
    run_id = uuid4()
    root_invocation_id = uuid4()
    child_invocation_id = uuid4()
    root_node_id = uuid4()
    child_node_id = uuid4()
    root_agent_id = uuid4()
    child_agent_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=3600)

    await publisher.publish(
        run_id,
        "network",
        "agent_invocation_started",
        {
            "invocation_id": str(root_invocation_id),
            "parent_invocation_id": None,
            "node_id": str(root_node_id),
            "agent_id": str(root_agent_id),
            "depth": 0,
            "label": "Root Agent",
            "provider": "custom",
            "model": "deepseek-v4-flash",
            "source": "draft",
            "version": "r4",
            "started_at": "2026-08-27T22:00:00Z",
        },
    )
    await publisher.publish(
        run_id,
        "network",
        "delegation_started",
        {
            "invocation_id": str(root_invocation_id),
            "target_node_id": str(child_node_id),
            "target": "Billing Agent",
            "task_fingerprint": "fingerprint-1",
        },
    )
    await publisher.publish(
        run_id,
        "network",
        "agent_invocation_started",
        {
            "invocation_id": str(child_invocation_id),
            "parent_invocation_id": str(root_invocation_id),
            "node_id": str(child_node_id),
            "agent_id": str(child_agent_id),
            "depth": 1,
            "label": "Billing Agent",
            "provider": "custom",
            "model": "deepseek-v4-flash",
            "source": "release",
            "version": "r4",
            "started_at": "2026-08-27T22:00:01Z",
        },
    )
    await publisher.publish(
        run_id,
        "network",
        "agent_invocation_completed",
        {
            "invocation_id": str(child_invocation_id),
            "parent_invocation_id": str(root_invocation_id),
            "node_id": str(child_node_id),
            "agent_id": str(child_agent_id),
            "depth": 1,
            "output": "sensitive full child output must not be projected",
            "tool_calls": [{"output": "raw tool result"}],
            "sources": [{"content": "raw source content"}],
            "provider": "custom",
            "model": "deepseek-v4-flash",
            "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            "completed_at": "2026-08-27T22:00:02Z",
        },
    )
    await publisher.publish(
        run_id,
        "network",
        "delegation_completed",
        {
            "invocation_id": str(root_invocation_id),
            "target_node_id": str(child_node_id),
            "target": "Billing Agent",
            "task_fingerprint": "fingerprint-1",
        },
    )

    reader = RuntimeStreamReader(store)
    projection, _ = await reader.current_state(
        run_id,
        "network",
        durable_fallback=lambda: None,
    )

    invocations = {item["id"]: item for item in projection["invocations"]}
    assert set(invocations) == {str(root_invocation_id), str(child_invocation_id)}
    assert invocations[str(root_invocation_id)]["label"] == "Root Agent"
    assert invocations[str(root_invocation_id)]["status"] == "running"
    child = invocations[str(child_invocation_id)]
    assert child["parent_invocation_id"] == str(root_invocation_id)
    assert child["label"] == "Billing Agent"
    assert child["status"] == "completed"
    assert child["usage"]["total_tokens"] == 18
    assert "output" not in child
    assert "tool_calls" not in child
    assert "sources" not in child

    assert projection["delegations"] == [
        {
            "id": "fingerprint-1",
            "parent_invocation_id": str(root_invocation_id),
            "target_node_id": str(child_node_id),
            "target": "Billing Agent",
            "status": "completed",
            "reason": None,
            "started_at": None,
            "completed_at": pytest.ANY,
        }
    ]


@pytest.mark.asyncio
async def test_network_projection_preserves_failed_invocation_cause_for_reattach() -> None:
    store = InMemoryExecutionStateStore()
    publisher = RuntimeEventPublisher(store, projection_interval_seconds=0)
    run_id = uuid4()
    invocation_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=3600)

    await publisher.publish(
        run_id,
        "network",
        "agent_invocation_started",
        {
            "invocation_id": str(invocation_id),
            "node_id": str(uuid4()),
            "agent_id": str(uuid4()),
            "depth": 0,
            "label": "Root Agent",
        },
    )
    await publisher.publish(
        run_id,
        "network",
        "agent_invocation_failed",
        {
            "invocation_id": str(invocation_id),
            "code": "agent_context_error",
            "stage": "agent_context_preparation",
            "message": "The Agent session continuity could not be restored for this Network Run.",
            "retryable": False,
        },
    )

    reader = RuntimeStreamReader(store)
    projection, _ = await reader.current_state(
        run_id,
        "network",
        durable_fallback=lambda: None,
    )

    invocation = projection["invocations"][0]
    assert invocation["status"] == "failed"
    assert invocation["failure"]["code"] == "agent_context_error"
    assert invocation["failure"]["stage"] == "agent_context_preparation"
