"""A stale Redis projection must not keep a durably finalized Run open."""
import asyncio
from uuid import uuid4

import pytest

from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime.observer import RuntimeObserver
from shared.runtime.contracts import RunReference


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["agent", "network"])
@pytest.mark.parametrize("status", ["completed", "failed", "cancelled", "timed_out", "uncertain"])
async def test_terminal_durable_fact_replaces_stale_hot_state_without_hot_sequence(kind, status):
    run_id, session_id = uuid4(), uuid4()
    store = InMemoryExecutionStateStore()
    await store.create(run_id, {"session_id": str(session_id), "status": "running"}, ttl_seconds=3600)
    await store.append_event(run_id, "token", {"content": "old"})

    async def durable():
        return {"session_id": str(session_id), "status": status, "output": "final", "result": {"answer": "final"}}

    observer = RuntimeObserver(store)
    run = RunReference.agent(run_id) if kind == "agent" else RunReference.network(run_id)
    stream = observer.observe(run, durable_fallback=durable)
    frame = await asyncio.wait_for(anext(stream), 1)
    assert frame.event_type == "run.state"
    assert frame.run_id == run_id and frame.session_id == session_id
    assert frame.data["status"] == status
    assert frame.data["output"] == "final"
    assert frame.data["sequence"] is None
    assert frame.data["realtime_available"] is False
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), 1)
    assert (await store.get(run_id))["status"] == "running"  # observation is read-only


@pytest.mark.asyncio
@pytest.mark.parametrize("tail_failure", [False, True])
async def test_run_finalizing_after_attach_closes_idle_hot_tail(monkeypatch, tail_failure):
    run_id, session_id = uuid4(), uuid4()
    store = InMemoryExecutionStateStore()
    await store.create(run_id, {"session_id": str(session_id), "status": "running"}, ttl_seconds=3600)
    await store.append_event(run_id, "token", {"content": "partial"})
    durable_state = {"session_id": str(session_id), "status": "running", "output": ""}

    async def durable():
        return dict(durable_state)

    observer = RuntimeObserver(store, block_ms=50)
    stream = observer.observe(RunReference.agent(run_id), durable_fallback=durable)
    first = await anext(stream)
    assert first.data["status"] == "running" and first.data["sequence"] == 1
    if tail_failure:
        async def unavailable(*args, **kwargs):
            raise ConnectionError("Redis unavailable")
        monkeypatch.setattr(store, "read_events_after_cursor", unavailable)
    durable_state.update(status="completed", output="final")
    terminal = await asyncio.wait_for(anext(stream), 2)
    assert terminal.data["status"] == "completed"
    assert terminal.data["sequence"] is None
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_unavailable_durable_probe_preserves_healthy_hot_terminal():
    run_id = uuid4()
    store = InMemoryExecutionStateStore()
    await store.create(run_id, {"status": "running", "session_id": str(uuid4())}, ttl_seconds=3600)
    await store.append_event(run_id, "execution_completed", {"output": "hot final"})

    async def unavailable():
        raise ConnectionError("Database temporarily unavailable")

    stream = RuntimeObserver(store).observe(RunReference.agent(run_id), durable_fallback=unavailable)
    frame = await anext(stream)
    assert frame.data["status"] == "completed" and frame.data["output"] == "hot final"
    assert frame.data["sequence"] == 1 and frame.data["realtime_available"]
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
