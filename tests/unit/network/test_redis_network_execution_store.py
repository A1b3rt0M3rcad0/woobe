from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


@pytest.mark.asyncio
async def test_network_store_keeps_invocations_context_cancel_and_terminal_state_outside_sql() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution_id = uuid4()
    network_session_id = uuid4()
    node_id = uuid4()
    agent_id = uuid4()
    existing_agent_session_id = uuid4()
    trace_id = uuid4()
    execution = NetworkExecutionSnapshot(
        id=execution_id,
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=network_session_id,
        project_id=uuid4(),
        input_message="network input",
        draft_revision=3,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={
            str(node_id): {"release_id": None, "session_mode": "stateful"}
        },
        status="queued",
    )

    await store.initialize(
        execution,
        ttl_seconds=3600,
        agent_contexts={str(node_id): str(existing_agent_session_id)},
    )
    invocation = await store.start_invocation(
        execution=execution,
        node_id=node_id,
        agent_id=agent_id,
        depth=0,
        message="agent input",
        parent_invocation_id=None,
        persist_context=True,
    )

    assert invocation.agent_session_id == existing_agent_session_id

    new_agent_session_id = uuid4()
    invocation_result = AgentInvocationResult(
        answer="agent output",
        session_id=new_agent_session_id,
        trace_id=trace_id,
        provider="openai",
        model="test-model",
        usage={
            "input_tokens": 2,
            "output_tokens": 3,
            "total_tokens": 5,
            "cost_usd": 0.001,
        },
        tool_calls=[{"tool_name": "lookup", "success": True}],
        sources=[{"chunk_id": str(uuid4())}],
    )
    object.__setattr__(
        invocation_result,
        "diagnostics",
        {
            "schema_version": 5,
            "llm_work_latency_ms": 12,
            "usage_complete": True,
            "cost_status": "known",
            "cost_usd": 0.001,
        },
    )
    object.__setattr__(
        invocation_result,
        "llm_calls",
        [{"call_id": "llm-1", "latency_ms": 12, "cost_status": "known"}],
    )
    object.__setattr__(
        invocation_result,
        "started_at",
        "2026-08-25T12:00:00+00:00",
    )
    object.__setattr__(
        invocation_result,
        "completed_at",
        "2026-08-25T12:00:01+00:00",
    )
    await store.complete_invocation(
        invocation.id,
        result=invocation_result,
        persist_context=True,
    )

    invocations = await store.invocations(execution_id)
    assert len(invocations) == 1
    persisted = invocations[0]
    assert persisted["id"] == str(invocation.id)
    assert persisted["agent_run_id"] == str(invocation.id)
    assert persisted["status"] == "completed"
    assert persisted["output_message"] == "agent output"
    assert persisted["agent_session_id"] == str(new_agent_session_id)
    assert persisted["trace_id"] == str(trace_id)
    assert persisted["usage"]["total_tokens"] == 5
    assert persisted["tool_calls"][0]["tool_name"] == "lookup"
    assert persisted["diagnostics"]["schema_version"] == 5
    assert persisted["diagnostics"]["llm_work_latency_ms"] == 12
    assert persisted["llm_calls"][0]["call_id"] == "llm-1"
    assert persisted["started_at"] == "2026-08-25T12:00:00+00:00"
    assert persisted["completed_at"] == "2026-08-25T12:00:01+00:00"

    snapshot = await store.snapshot(execution_id)
    assert snapshot[f"agent_session:{node_id}"] == str(new_agent_session_id)
    assert snapshot["invocation_count"] == 1

    await store.request_cancel(execution_id)
    assert await store.is_cancel_requested(execution_id) is True

    await store.mark_terminal_pending(
        execution_id,
        status="completed",
        result={"output": "network output", "trace_id": str(trace_id)},
    )
    terminal = await store.snapshot(execution_id)
    assert terminal["status"] == "terminal_pending_persist"
    assert terminal["terminal_status"] == "completed"
    assert terminal["terminal_result"]["output"] == "network output"

    await store.mark_persisted(execution_id, status="completed")
    final_state = await store.snapshot(execution_id)
    assert final_state["status"] == "completed"
    assert final_state["phase"] == "persisted"
