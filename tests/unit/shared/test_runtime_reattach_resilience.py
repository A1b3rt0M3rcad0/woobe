from __future__ import annotations

from uuid import uuid4

import pytest

from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime import RuntimeEventPublisher, RuntimeStreamReader


@pytest.mark.asyncio
async def test_multiple_observers_receive_same_live_event_independently() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=3600)
    await store.append_event(run_id, "token", {"content": "1"})

    reader_a = RuntimeStreamReader(store, block_ms=20)
    reader_b = RuntimeStreamReader(store, block_ms=20)
    stream_a = reader_a.stream(run_id, "agent", durable_fallback=lambda: None)
    stream_b = reader_b.stream(run_id, "agent", durable_fallback=lambda: None)

    state_a = await anext(stream_a)
    state_b = await anext(stream_b)
    assert state_a.sequence == 1
    assert state_b.sequence == 1

    await store.append_event(run_id, "token", {"content": "2"})
    live_a = await anext(stream_a)
    live_b = await anext(stream_b)

    assert live_a.sequence == 2
    assert live_b.sequence == 2
    assert live_a.data["content"] == "2"
    assert live_b.data["content"] == "2"

    await stream_a.aclose()
    await stream_b.aclose()


@pytest.mark.asyncio
async def test_reattach_snapshot_and_live_tail_do_not_duplicate_materialized_output() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=3600)
    await store.append_event(
        run_id,
        "token",
        {
            "content": "Hello",
            "visibility": "assistant",
            "channel": "final",
        },
    )

    reader = RuntimeStreamReader(store, block_ms=20)
    stream = reader.stream(run_id, "agent", durable_fallback=lambda: None)

    snapshot = await anext(stream)
    assert snapshot.event_type == "run.state"
    assert snapshot.sequence == 1
    assert snapshot.data["output"] == "Hello"

    # Anything materialized into the replacement snapshot is behind the cursor that
    # starts the live tail. Only a genuinely newer event may be delivered next.
    await store.append_event(
        run_id,
        "token",
        {
            "content": " world",
            "visibility": "assistant",
            "channel": "final",
        },
    )
    live = await anext(stream)

    assert live.event_type == "token"
    assert live.sequence == 2
    assert live.data["content"] == " world"
    assert live.data["content"] != "Hello"

    await store.append_event(
        run_id,
        "done",
        {"answer": "Hello world"},
    )
    terminal = await anext(stream)
    assert terminal.event_type == "done"
    assert terminal.sequence == 3

    await stream.aclose()


class _UnavailableStore:
    async def get(self, _run_id):
        raise RuntimeError("redis unavailable")


@pytest.mark.asyncio
async def test_unavailable_hot_store_degrades_to_durable_state_without_run_failure() -> None:
    run_id = uuid4()
    reader = RuntimeStreamReader(_UnavailableStore())

    async def fallback():
        return {
            "status": "running",
            "output": "durable partial",
            "result": None,
        }

    stream = reader.stream(run_id, "agent", durable_fallback=fallback)
    state = await anext(stream)

    assert state.event_type == "run.state"
    assert state.data["status"] == "running"
    assert state.data["output"] == "durable partial"
    assert state.data["realtime_available"] is False

    with pytest.raises(StopAsyncIteration):
        await anext(stream)


class _FailingPublisherStore:
    async def append_event(self, *_args, **_kwargs):
        raise RuntimeError("redis write failed")


@pytest.mark.asyncio
async def test_realtime_event_publication_failure_is_best_effort() -> None:
    publisher = RuntimeEventPublisher(_FailingPublisherStore())

    result = await publisher.publish(
        uuid4(),
        "agent",
        "token",
        {"content": "answer"},
    )

    assert result is None
