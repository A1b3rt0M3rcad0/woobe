from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.runtime import RunKind, RunReference, RuntimeFrame, RuntimeObserver


@dataclass(frozen=True)
class _Event:
    event_type: str
    payload: dict[str, Any]


class _LiveSource:
    def __init__(self) -> None:
        self.observers: set[asyncio.Queue[_Event]] = set()

    def subscribe(self) -> asyncio.Queue[_Event]:
        queue: asyncio.Queue[_Event] = asyncio.Queue()
        self.observers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[_Event]) -> None:
        self.observers.discard(queue)

    async def emit(self, event_type: str, **payload: Any) -> None:
        event = _Event(event_type, payload)
        for observer in tuple(self.observers):
            observer.put_nowait(event)


@pytest.mark.asyncio
async def test_observer_uses_canonical_run_reference_for_hot_reattach() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    await store.create(run_id, {"status": "running"}, ttl_seconds=60)
    await store.append_event(run_id, "token", {"content": "hello"})

    observer = RuntimeObserver(store, block_ms=20)

    async def durable_fallback():
        return {"status": "completed", "output": "durable"}

    stream = observer.observe(
        RunReference.agent(run_id),
        durable_fallback=durable_fallback,
    )
    state = await anext(stream)

    assert state == RuntimeFrame(
        event_type="run.state",
        data=state.data,
        sequence=1,
    )
    assert state.data["kind"] == "AGENT"
    assert state.data["output"] == "hello"
    await stream.aclose()


@pytest.mark.asyncio
async def test_observer_waits_between_durable_acceptance_and_hot_runtime() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    durable = {"status": "queued", "output": ""}
    observer = RuntimeObserver(store, block_ms=20, local_poll_seconds=0.01)

    async def durable_fallback():
        return dict(durable)

    stream = observer.observe(
        RunReference.network(run_id),
        durable_fallback=durable_fallback,
    )
    accepted = await asyncio.wait_for(anext(stream), timeout=1)

    assert accepted.event_type == "run.state"
    assert accepted.data["status"] == "queued"
    assert accepted.data["realtime_available"] is False

    await store.create(run_id, {"status": "running"}, ttl_seconds=60)
    await store.append_event(run_id, "execution_started", {})

    hot = await asyncio.wait_for(anext(stream), timeout=1)
    assert hot.event_type == "run.state"
    assert hot.data["status"] == "running"
    assert hot.data["realtime_available"] is True
    await stream.aclose()


@pytest.mark.asyncio
async def test_observer_emits_durable_terminal_if_hot_runtime_never_materializes() -> None:
    store = InMemoryExecutionStateStore()
    run_id = uuid4()
    durable = {"status": "queued", "output": ""}
    observer = RuntimeObserver(store, block_ms=20, local_poll_seconds=0.01)

    async def durable_fallback():
        return dict(durable)

    stream = observer.observe(
        RunReference.network(run_id),
        durable_fallback=durable_fallback,
    )
    _ = await asyncio.wait_for(anext(stream), timeout=1)
    durable.update({"status": "completed", "output": "done"})

    terminal = await asyncio.wait_for(anext(stream), timeout=1)
    assert terminal.event_type == "run.state"
    assert terminal.data["status"] == "completed"
    assert terminal.data["output"] == "done"
    assert terminal.data["realtime_available"] is False

    with pytest.raises(StopAsyncIteration):
        await anext(stream)


@pytest.mark.asyncio
async def test_local_subscription_is_observer_only_and_does_not_own_source() -> None:
    store = InMemoryExecutionStateStore()
    observer = RuntimeObserver(store, heartbeat_seconds=60, local_poll_seconds=0.01)
    source = _LiveSource()
    run_id = uuid4()

    subscription = observer.subscribe_local(
        source,
        run_kind=RunKind.AGENT,
        run_id_resolver=lambda: run_id,
    )
    stream = subscription.stream()

    await source.emit("token", content="first")
    frame = await asyncio.wait_for(anext(stream), timeout=1)
    assert frame.event_type == "token"
    assert frame.sequence is None
    assert frame.data["run_id"] == str(run_id)
    assert frame.data["content"] == "first"

    await source.emit("done", answer="first")
    terminal = await asyncio.wait_for(anext(stream), timeout=1)
    assert terminal.event_type == "done"

    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert source.observers == set()
