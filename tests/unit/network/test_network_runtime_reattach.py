from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime_reattach import RuntimeStreamReader


def _execution(execution_id):
    return NetworkExecutionSnapshot(
        id=execution_id,
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="network input",
        draft_revision=1,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={},
        status="queued",
    )


@pytest.mark.asyncio
async def test_network_terminal_event_is_visible_only_after_persisted_boundary() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution_id = uuid4()
    execution = _execution(execution_id)
    await store.initialize(execution, ttl_seconds=3600)
    await store.emit(
        execution_id,
        "token",
        {"content": "hello ", "visibility": "assistant", "channel": "final"},
    )
    await store.emit(
        execution_id,
        "token",
        {"content": "world", "visibility": "assistant", "channel": "final"},
    )
    await store.persist_execution_output(
        execution_id,
        AgentInvocationResult(
            answer="hello world",
            trace_id=uuid4(),
            parsed_output={"answer": "hello world", "confidence": 0.9},
            output_parse_error=None,
        ),
    )
    await store.mark_terminal_pending(
        execution_id,
        status="completed",
        result={"output": "hello world", "trace_id": str(uuid4())},
    )

    pending_events = await state.list_events_after(execution_id, 0)
    assert pending_events[-1].event_type != "execution_completed"

    await store.mark_persisted(execution_id, status="completed")

    events = await state.list_events_after(execution_id, 0)
    assert events[-1].event_type == "execution_completed"
    assert events[-1].payload["parsed_output"] == {
        "answer": "hello world",
        "confidence": 0.9,
    }

    reader = RuntimeStreamReader(state, block_ms=20)
    stream = reader.stream(
        execution_id,
        "network",
        durable_fallback=lambda: None,
    )
    frame = await anext(stream)
    assert frame.event_type == "run.state"
    assert frame.data["status"] == "completed"
    assert frame.data["output"] == "hello world"
    assert frame.data["parsed_output"] == {
        "answer": "hello world",
        "confidence": 0.9,
    }

    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_network_hot_events_keep_invocation_causal_metadata() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution_id = uuid4()
    execution = _execution(execution_id)
    node_id = uuid4()
    agent_id = uuid4()
    parent_invocation_id = uuid4()

    await store.initialize(execution, ttl_seconds=3600)
    invocation = await store.start_invocation(
        execution=execution,
        node_id=node_id,
        agent_id=agent_id,
        depth=2,
        message="delegated input",
        parent_invocation_id=parent_invocation_id,
        persist_context=False,
    )
    await store.emit(
        execution_id,
        "agent_activity",
        {"status": "working"},
        invocation_id=invocation.id,
    )

    events = await state.list_events_after(execution_id, 0)
    activity = next(event for event in events if event.event_type == "agent_activity")
    assert activity.payload["invocation_id"] == str(invocation.id)
    assert activity.payload["parent_invocation_id"] == str(parent_invocation_id)
    assert activity.payload["node_id"] == str(node_id)
    assert activity.payload["agent_id"] == str(agent_id)
    assert activity.payload["depth"] == 2
