from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from woobe_workers.consumers.network.execution_worker import NetworkLeaseRecoveryWorker


class _Loader:
    def __init__(self, loaded) -> None:
        self.loaded = loaded
        self.candidate_calls: list[int] = []

    async def recovery_candidates(self, *, older_than_seconds: int):
        self.candidate_calls.append(older_than_seconds)
        return [self.loaded.execution.id]

    async def load(self, execution_id):
        return self.loaded if execution_id == self.loaded.execution.id else None


class _Store:
    def __init__(self, *, state: dict, invocations: list[dict] | None = None, lease=True) -> None:
        self.state = state
        self.invocation_states = list(invocations or [])
        self.lease = lease
        self.persisted: list[tuple[object, str]] = []
        self.lease_calls = 0

    async def snapshot(self, _execution_id):
        return dict(self.state)

    async def invocations(self, _execution_id):
        return [dict(item) for item in self.invocation_states]

    async def acquire_lease(self, execution_id, *, worker_id, ttl_seconds):
        del execution_id, worker_id, ttl_seconds
        self.lease_calls += 1
        return SimpleNamespace(owner="recovery", generation=1) if self.lease else None

    async def mark_persisted(self, execution_id, *, status):
        self.persisted.append((execution_id, status))


class _Finalizer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def finalize(self, **kwargs):
        self.calls.append(kwargs)
        return True


def _loaded(*, status: str = "running"):
    execution = SimpleNamespace(id=uuid4(), status=status)
    return SimpleNamespace(execution=execution, version=SimpleNamespace(id=uuid4()))


def _worker(*, loaded, store, finalizer):
    return NetworkLeaseRecoveryWorker(
        loader=_Loader(loaded),
        store=store,
        finalizer=finalizer,
        lease_ttl_seconds=10,
    )


@pytest.mark.asyncio
async def test_recovery_marks_started_execution_uncertain_when_hot_state_disappeared() -> None:
    loaded = _loaded(status="running")
    store = _Store(state={})
    finalizer = _Finalizer()
    worker = _worker(loaded=loaded, store=store, finalizer=finalizer)

    await worker.run()

    assert len(finalizer.calls) == 1
    call = finalizer.calls[0]
    assert call["execution_id"] == loaded.execution.id
    assert call["failure_code"] == "execution_state_lost"
    assert call["uncertain"] is True
    assert store.lease_calls == 0
    assert store.persisted == []


@pytest.mark.asyncio
async def test_recovery_resumes_terminal_pending_cancelled_without_replaying_execution() -> None:
    loaded = _loaded(status="running")
    trace_id = uuid4()
    store = _Store(
        state={
            "status": "terminal_pending_persist",
            "terminal_status": "cancelled",
            "terminal_result": {
                "output": "partial",
                "trace_id": str(trace_id),
                "partial": True,
                "cancelled": True,
            },
        },
        invocations=[{"id": str(uuid4()), "status": "cancelled"}],
    )
    finalizer = _Finalizer()
    worker = _worker(loaded=loaded, store=store, finalizer=finalizer)

    await worker.run()

    assert len(finalizer.calls) == 1
    call = finalizer.calls[0]
    assert call["terminal_status"] == "cancelled"
    assert call["output"] == "partial"
    assert call["trace_id"] == trace_id
    assert store.lease_calls == 0
    assert store.persisted == [(loaded.execution.id, "cancelled")]


@pytest.mark.asyncio
async def test_recovery_fences_expired_worker_with_existing_invocations_as_uncertain() -> None:
    loaded = _loaded(status="running")
    store = _Store(
        state={"status": "running"},
        invocations=[{"id": str(uuid4()), "status": "running"}],
        lease=True,
    )
    finalizer = _Finalizer()
    worker = _worker(loaded=loaded, store=store, finalizer=finalizer)

    await worker.run()

    assert store.lease_calls == 1
    assert len(finalizer.calls) == 1
    call = finalizer.calls[0]
    assert call["failure_code"] == "worker_lease_expired"
    assert call["uncertain"] is True
    assert store.persisted == [(loaded.execution.id, "uncertain")]
