from __future__ import annotations

from uuid import uuid4

import pytest

from woobe_workers.consumers.network.execution_worker import NetworkExecutionProcessor


class _Store:
    def __init__(self, trace_id) -> None:
        self.trace_id = trace_id
        self.pending = []
        self.persisted = []

    async def cancel_running_invocations(self, _execution_id) -> None:
        return None

    async def partial_output(self, _execution_id) -> str:
        return "partial network output"

    async def invocations(self, _execution_id):
        return [
            {
                "id": str(uuid4()),
                "depth": 0,
                "status": "cancelled",
                "trace_id": str(self.trace_id),
                "output_message": "partial network output",
            }
        ]

    async def mark_terminal_pending(self, execution_id, *, status, result) -> None:
        self.pending.append((execution_id, status, result))

    async def mark_persisted(self, execution_id, *, status) -> None:
        self.persisted.append((execution_id, status))


class _FailingFinalizer:
    async def finalize(self, **_kwargs) -> None:
        raise RuntimeError("postgres network finalization failed")


@pytest.mark.asyncio
async def test_network_cancellation_does_not_publish_persisted_terminal_when_postgres_finalization_fails() -> None:
    execution_id = uuid4()
    trace_id = uuid4()
    store = _Store(trace_id)
    processor = object.__new__(NetworkExecutionProcessor)
    processor._store = store
    processor._finalizer = _FailingFinalizer()

    with pytest.raises(RuntimeError, match="postgres network finalization failed"):
        await processor._terminal_cancelled(execution_id, version=None)

    assert len(store.pending) == 1
    assert store.pending[0][0] == execution_id
    assert store.pending[0][1] == "cancelled"
    assert store.persisted == []
