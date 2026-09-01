from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionCancelled,
    NetworkExecutionSnapshot,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


@pytest.mark.asyncio
async def test_cancel_fence_blocks_late_provider_events_and_invocation_completion() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="cancel while provider ignores interruption",
        draft_revision=1,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={},
        status="queued",
    )
    node_id = uuid4()
    agent_id = uuid4()

    await store.initialize(execution, ttl_seconds=3600)
    invocation = await store.start_invocation(
        execution=execution,
        node_id=node_id,
        agent_id=agent_id,
        depth=0,
        message=execution.input_message,
        parent_invocation_id=None,
        persist_context=False,
    )
    await store.emit(
        execution.id,
        "token",
        {
            "content": "accepted partial",
            "visibility": "assistant",
            "channel": "final",
            "phase": "response_generation",
        },
        invocation_id=invocation.id,
    )

    store.fence_execution(execution.id)
    await store.cancel_running_invocations(execution.id)
    fenced_snapshot = await store.snapshot(execution.id)
    fenced_sequence = int(fenced_snapshot.get("event_sequence") or 0)

    late_result = AgentInvocationResult(
        answer="late provider answer",
        session_id=None,
        trace_id=uuid4(),
        provider="openai",
        model="late-model",
        usage=None,
        tool_calls=[],
        sources=[],
    )
    await store.complete_invocation(
        invocation.id,
        result=late_result,
        persist_context=False,
    )
    await store.emit(
        execution.id,
        "token",
        {
            "content": " MUST NOT APPEAR",
            "visibility": "assistant",
            "channel": "final",
            "phase": "response_generation",
        },
        invocation_id=invocation.id,
    )

    with pytest.raises(NetworkExecutionCancelled):
        await store.start_invocation(
            execution=execution,
            node_id=uuid4(),
            agent_id=uuid4(),
            depth=1,
            message="late delegation",
            parent_invocation_id=invocation.id,
            persist_context=False,
        )

    final_snapshot = await store.snapshot(execution.id)
    persisted_invocation = (await store.invocations(execution.id))[0]

    assert persisted_invocation["status"] == "cancelled"
    assert persisted_invocation.get("output_message") == "accepted partial"
    assert await store.partial_output(execution.id) == "accepted partial"
    assert int(final_snapshot.get("event_sequence") or 0) == fenced_sequence

    store.release_execution_fence(execution.id)
