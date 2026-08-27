from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from modules.network.application.runtime import NetworkExecutionCancelled
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor


class _CancellationStore:
    def __init__(self) -> None:
        self.cancel_running_calls = 0

    async def is_cancel_requested(self, _execution_id) -> bool:
        return True

    async def cancel_running_invocations(self, _execution_id) -> None:
        self.cancel_running_calls += 1


@pytest.mark.asyncio
async def test_network_cancellation_interrupts_blocked_active_execution() -> None:
    execution_id = uuid4()
    store = _CancellationStore()
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store
    started = asyncio.Event()
    interrupted = asyncio.Event()

    async def blocked_execution():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            interrupted.set()
            raise

    execution = blocked_execution()
    task = asyncio.create_task(
        processor._execute_with_cancellation(execution_id, execution)
    )
    await asyncio.wait_for(started.wait(), timeout=1)

    with pytest.raises(NetworkExecutionCancelled):
        await asyncio.wait_for(task, timeout=1)

    assert interrupted.is_set()
    assert store.cancel_running_calls == 1


class _TerminalStore:
    def __init__(self, trace_id) -> None:
        self.trace_id = trace_id
        self.cancel_running_calls = 0
        self.pending = []
        self.persisted = []

    async def cancel_running_invocations(self, _execution_id) -> None:
        self.cancel_running_calls += 1

    async def partial_output(self, _execution_id) -> str:
        return "partial network answer"

    async def invocations(self, _execution_id):
        return [
            {
                "id": str(uuid4()),
                "depth": 0,
                "status": "cancelled",
                "trace_id": str(self.trace_id),
            }
        ]

    async def mark_terminal_pending(self, execution_id, *, status, result) -> None:
        self.pending.append((execution_id, status, result))

    async def mark_persisted(self, execution_id, *, status) -> None:
        self.persisted.append((execution_id, status))


class _Finalizer:
    def __init__(self) -> None:
        self.calls = []

    async def finalize(self, **kwargs) -> None:
        self.calls.append(kwargs)


@pytest.mark.asyncio
async def test_network_cancelled_finalization_preserves_partial_output_without_failure_semantics() -> None:
    execution_id = uuid4()
    trace_id = uuid4()
    store = _TerminalStore(trace_id)
    finalizer = _Finalizer()
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store
    processor._finalizer = finalizer

    await processor._terminal_cancelled(execution_id, version=None)

    assert store.cancel_running_calls == 1
    assert store.pending == [
        (
            execution_id,
            "cancelled",
            {
                "output": "partial network answer",
                "trace_id": str(trace_id),
                "partial": True,
                "cancelled": True,
            },
        )
    ]
    assert len(finalizer.calls) == 1
    assert finalizer.calls[0]["terminal_status"] == "cancelled"
    assert finalizer.calls[0]["output"] == "partial network answer"
    assert finalizer.calls[0]["trace_id"] == trace_id
    assert "failure_code" not in finalizer.calls[0]
    assert "failure_detail" not in finalizer.calls[0]
    assert store.persisted == [(execution_id, "cancelled")]
