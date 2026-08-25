from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import NetworkExecutionSnapshot
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime_reattach import RuntimeStreamReader


@pytest.mark.asyncio
async def test_network_terminal_event_is_visible_only_after_persisted_boundary() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution_id = uuid4()
    execution = NetworkExecutionSnapshot(
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

    with pytest.raises(StopAsyncIteration):
        await anext(stream)
