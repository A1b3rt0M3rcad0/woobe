from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from modules.network.application.runtime import NetworkExecutionCancelled
from woobe_workers.consumers.network.execution_worker import NetworkExecutionProcessor


class _CancellationStore:
    def __init__(self) -> None:
        self.fenced: list[object] = []
        self.released: list[object] = []
        self.cancel_running_calls = 0

    async def is_cancel_requested(self, _execution_id) -> bool:
        return True

    def fence_execution(self, execution_id) -> None:
        self.fenced.append(execution_id)

    def release_execution_fence(self, execution_id) -> None:
        self.released.append(execution_id)

    async def cancel_running_invocations(self, _execution_id) -> None:
        self.cancel_running_calls += 1


@pytest.mark.asyncio
async def test_network_cancel_does_not_wait_forever_for_provider_that_swallows_cancel() -> None:
    execution_id = uuid4()
    store = _CancellationStore()
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store

    started = asyncio.Event()
    release = asyncio.Event()
    finished = asyncio.Event()
    cancel_count = 0

    async def stubborn_execution():
        nonlocal cancel_count
        started.set()
        while not release.is_set():
            try:
                await asyncio.wait_for(release.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                cancel_count += 1
                continue
        finished.set()
        return object()

    task = asyncio.create_task(
        processor._execute_with_cancellation(execution_id, stubborn_execution())
    )
    await asyncio.wait_for(started.wait(), timeout=1)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=1)

    assert cancel_count >= 1
    assert store.cancel_running_calls == 1
    assert store.fenced == [execution_id]
    assert not finished.is_set()

    release.set()
    await asyncio.wait_for(finished.wait(), timeout=1)
    await asyncio.sleep(0)

    assert store.released == [execution_id]
