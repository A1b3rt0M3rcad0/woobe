from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.infra.workers.execution_worker import NetworkLeaseRecoveryWorker
from shared.contracts.execution_state import ExecutionLease


class _Loader:
    def __init__(self, execution_id, *, status: str, version=None) -> None:
        self.execution_id = execution_id
        self.loaded = SimpleNamespace(
            execution=SimpleNamespace(id=execution_id, status=status),
            version=version,
        )

    async def recovery_candidates(self, *, older_than_seconds: int):
        assert older_than_seconds >= 30
        return [self.execution_id]

    async def load(self, execution_id):
        assert execution_id == self.execution_id
        return self.loaded


class _Store:
    def __init__(self, state=None, invocations=None, *, lease_available=True) -> None:
        self.state = dict(state or {})
        self.invocation_values = list(invocations or [])
        self.lease_available = lease_available
        self.persisted = []
        self.lease_requests = 0

    async def snapshot(self, _execution_id):
        return dict(self.state)

    async def invocations(self, _execution_id):
        return list(self.invocation_values)

    async def acquire_lease(self, _execution_id, *, worker_id, ttl_seconds):
        self.lease_requests += 1
        if not self.lease_available:
            return None
        return ExecutionLease(owner=worker_id, generation=1)

    async def mark_persisted(self, execution_id, *, status, ttl_seconds=900):
        self.persisted.append((execution_id, status, ttl_seconds))


class _Finalizer:
    def __init__(self) -> None:
        self.calls = []

    async def finalize(self, **kwargs):
        self.calls.append(dict(kwargs))
        return True


def _worker(execution_id, *, status, state=None, invocations=None, lease_available=True):
    loader = _Loader(execution_id, status=status)
    store = _Store(state, invocations, lease_available=lease_available)
    finalizer = _Finalizer()
    worker = NetworkLeaseRecoveryWorker(
        loader=loader,
        store=store,
        finalizer=finalizer,
        lease_ttl_seconds=15,
    )
    return worker, store, finalizer


@pytest.mark.asyncio
async def test_terminal_pending_persist_replays_only_finalization() -> None:
    execution_id = uuid4()
    trace_id = uuid4()
    invocation_id = uuid4()
    worker, store, finalizer = _worker(
        execution_id,
        status="queued",
        state={
            "status": "terminal_pending_persist",
            "terminal_status": "completed",
            "terminal_result": {
                "output": "done",
                "trace_id": str(trace_id),
                "streamed_output": True,
            },
        },
        invocations=[{"id": str(invocation_id), "status": "completed"}],
    )

    await worker.run()

    assert len(finalizer.calls) == 1
    call = finalizer.calls[0]
    assert call["execution_id"] == execution_id
    assert call["terminal_status"] == "completed"
    assert call["output"] == "done"
    assert call["trace_id"] == trace_id
    assert call["streamed_output"] is True
    assert call["invocation_states"] == [
        {"id": str(invocation_id), "status": "completed"}
    ]
    assert store.lease_requests == 0, "terminal persistence recovery must not resume execution"
    assert store.persisted[-1][1] == "completed"


@pytest.mark.asyncio
async def test_old_queued_execution_without_redis_state_is_not_marked_uncertain() -> None:
    execution_id = uuid4()
    worker, store, finalizer = _worker(execution_id, status="queued")

    await worker.run()

    assert finalizer.calls == []
    assert store.lease_requests == 0
    assert store.persisted == []


@pytest.mark.asyncio
async def test_running_execution_without_redis_state_becomes_uncertain_without_replay() -> None:
    execution_id = uuid4()
    worker, store, finalizer = _worker(execution_id, status="running")

    await worker.run()

    assert len(finalizer.calls) == 1
    call = finalizer.calls[0]
    assert call["failure_code"] == "execution_state_lost"
    assert call["uncertain"] is True
    assert call["invocation_states"] == []
    assert store.lease_requests == 0


@pytest.mark.asyncio
async def test_expired_lease_with_invocations_is_uncertain() -> None:
    execution_id = uuid4()
    worker, store, finalizer = _worker(
        execution_id,
        status="queued",
        state={"status": "running"},
        invocations=[{"id": str(uuid4()), "status": "running"}],
    )

    await worker.run()

    assert store.lease_requests == 1
    assert len(finalizer.calls) == 1
    call = finalizer.calls[0]
    assert call["failure_code"] == "worker_lease_expired"
    assert call["uncertain"] is True
    assert store.persisted[-1][1] == "uncertain"


@pytest.mark.asyncio
async def test_expired_lease_without_invocations_is_failed_not_uncertain() -> None:
    execution_id = uuid4()
    worker, store, finalizer = _worker(
        execution_id,
        status="queued",
        state={"status": "running"},
        invocations=[],
    )

    await worker.run()

    assert len(finalizer.calls) == 1
    call = finalizer.calls[0]
    assert call["failure_code"] == "worker_lease_expired"
    assert call["uncertain"] is False
    assert store.persisted[-1][1] == "failed"
