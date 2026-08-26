from __future__ import annotations

from uuid import uuid4

import pytest

from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime_reattach import RuntimeStreamGapError, RuntimeStreamReader


async def _completed_fallback(run_id):
    return {
        "run_id": str(run_id),
        "status": "completed",
        "output": "durable answer",
        "result": {"answer": "durable answer"},
    }


@pytest.mark.asyncio
async def test_reattach_folds_125_to_131_into_initial_state_then_tails_132() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=3600)

    for sequence in range(1, 132):
        await store.append_event(run_id, "token", {"content": f"{sequence},"})

    await store.update(
        run_id,
        {
            "runtime_projection": {
                "run_id": str(run_id),
                "kind": "AGENT",
                "status": "running",
                "sequence": 125,
                "output": "".join(f"{value}," for value in range(1, 126)),
                "activity": None,
                "active_tools": [],
                "active_agents": [],
                "completed_agents": [],
                "current_route": None,
                "usage": {},
                "result": None,
            }
        },
    )

    reader = RuntimeStreamReader(store, block_ms=20)
    stream = reader.stream(
        run_id,
        "agent",
        durable_fallback=lambda: _completed_fallback(run_id),
    )

    state = await anext(stream)
    assert state.event_type == "run.state"
    assert state.sequence == 131
    assert state.data["sequence"] == 131
    assert state.data["output"].endswith("126,127,128,129,130,131,")
    hot = await store.get(run_id)
    assert hot is not None
    assert hot["reattach_count"] == 1

    await store.append_event(run_id, "token", {"content": "132,"})
    live = await anext(stream)
    assert live.event_type == "token"
    assert live.sequence == 132
    assert live.data["content"] == "132,"
    await stream.aclose()


@pytest.mark.asyncio
async def test_events_published_after_high_watermark_are_not_lost() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=3600)
    for sequence in range(1, 132):
        await store.append_event(run_id, "token", {"content": str(sequence)})

    reader = RuntimeStreamReader(store, block_ms=20)
    stream = reader.stream(
        run_id,
        "network",
        durable_fallback=lambda: _completed_fallback(run_id),
    )
    state = await anext(stream)
    assert state.sequence == 131

    await store.append_event(run_id, "token", {"content": "132"})
    await store.append_event(run_id, "token", {"content": "133"})

    event_132 = await anext(stream)
    event_133 = await anext(stream)
    assert [event_132.sequence, event_133.sequence] == [132, 133]
    await stream.aclose()


@pytest.mark.asyncio
async def test_trim_gap_is_detected_instead_of_inventing_continuity() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=3600)
    for sequence in range(1, 6):
        await store.append_event(
            run_id,
            "token",
            {"content": str(sequence)},
            maxlen=3,
        )
    await store.update(
        run_id,
        {
            "runtime_projection": {
                "run_id": str(run_id),
                "kind": "AGENT",
                "status": "running",
                "sequence": 1,
                "output": "1",
            }
        },
    )

    reader = RuntimeStreamReader(store)
    with pytest.raises(RuntimeStreamGapError):
        await reader.current_state(
            run_id,
            "agent",
            durable_fallback=lambda: _completed_fallback(run_id),
        )


@pytest.mark.asyncio
async def test_terminal_run_falls_back_to_durable_state_after_hot_state_expires() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    reader = RuntimeStreamReader(store)
    stream = reader.stream(
        run_id,
        "agent",
        durable_fallback=lambda: _completed_fallback(run_id),
    )

    state = await anext(stream)
    assert state.event_type == "run.state"
    assert state.data["status"] == "completed"
    assert state.data["output"] == "durable answer"
    assert state.data["realtime_available"] is False

    with pytest.raises(StopAsyncIteration):
        await anext(stream)
