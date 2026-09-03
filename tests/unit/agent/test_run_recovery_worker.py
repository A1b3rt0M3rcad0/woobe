from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from woobe_workers.consumers.agent import run_recovery_worker as recovery_module
from woobe_workers.consumers.agent.registry import AgentWorkerRegistry, register_agent_workers
from woobe_workers.consumers.agent.run_recovery_worker import AgentRunRecoveryWorker


class _ScalarResult:
    def __init__(self, *, values=None, value=None) -> None:
        self._values = list(values or [])
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return list(self._values)

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, result: _ScalarResult) -> None:
        self._result = result

    async def execute(self, _statement):
        return self._result


class _FakeUow:
    def __init__(self, result: _ScalarResult) -> None:
        self.session = _FakeSession(result)

    def mark_read_only(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _StateStore:
    def __init__(self, value=None, error: Exception | None = None) -> None:
        self.value = value
        self.error = error
        self.reads: list[object] = []

    async def get(self, run_id):
        self.reads.append(run_id)
        if self.error is not None:
            raise self.error
        return self.value


def _run(*, network_execution_id=None):
    return SimpleNamespace(
        id=uuid4(),
        status="running",
        network_execution_id=network_execution_id,
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        trace_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        failure_code=None,
        failure_detail=None,
        result=None,
        completed_at=None,
    )


def _install_fake_uows(monkeypatch, results: list[_ScalarResult]) -> None:
    pending = list(results)

    def build(_engine):
        if not pending:
            raise AssertionError("Unexpected AgentUnitOfWork construction")
        return _FakeUow(pending.pop(0))

    monkeypatch.setattr(recovery_module, "AgentUnitOfWork", build)


def test_recovery_worker_is_registered_even_without_rabbitmq() -> None:
    registry = AgentWorkerRegistry()
    settings = MagicMock()
    settings.runtime_total_timeout_seconds = 120.0

    register_agent_workers(
        registry,
        settings=settings,
        engine=MagicMock(),
        rabbitmq_manager=None,
    )

    workers = registry.iter_workers()
    recovery = next(worker for worker in workers if isinstance(worker, AgentRunRecoveryWorker))
    assert recovery._stale_after_seconds == 900.0


@pytest.mark.asyncio
async def test_orphaned_standalone_run_is_finalized_as_uncertain(monkeypatch) -> None:
    run = _run()
    _install_fake_uows(
        monkeypatch,
        [
            _ScalarResult(values=[run.id]),
            _ScalarResult(value=run),
        ],
    )
    events = []

    class _Writer:
        def __init__(self, _uow) -> None:
            pass

        async def write(self, event) -> None:
            events.append(event)

    monkeypatch.setattr(recovery_module, "SQLAlchemyAgentOutboxEventWriter", _Writer)
    worker = AgentRunRecoveryWorker(
        async_engine=MagicMock(),
        state_store=_StateStore(value=None),
        stale_after_seconds=60,
    )

    await worker.run()

    assert run.status == "uncertain"
    assert run.failure_code == "runtime_state_lost"
    assert "cannot be proven" in run.failure_detail
    assert run.result["uncertain"] is True
    assert run.result["run_id"] == str(run.id)
    assert run.completed_at is not None
    assert len(events) == 1
    assert events[0].event_type == "agent.execution.failed.v1"


@pytest.mark.asyncio
async def test_recovery_does_not_touch_run_with_hot_runtime_state(monkeypatch) -> None:
    run = _run()
    _install_fake_uows(monkeypatch, [_ScalarResult(values=[run.id])])
    worker = AgentRunRecoveryWorker(
        async_engine=MagicMock(),
        state_store=_StateStore(value={"status": "running"}),
        stale_after_seconds=60,
    )

    await worker.run()

    assert run.status == "running"
    assert run.completed_at is None


@pytest.mark.asyncio
async def test_recovery_defers_when_hot_state_backend_is_unavailable(monkeypatch) -> None:
    run = _run()
    _install_fake_uows(monkeypatch, [_ScalarResult(values=[run.id])])
    worker = AgentRunRecoveryWorker(
        async_engine=MagicMock(),
        state_store=_StateStore(error=RuntimeError("redis unavailable")),
        stale_after_seconds=60,
    )

    await worker.run()

    assert run.status == "running"
    assert run.completed_at is None


@pytest.mark.asyncio
async def test_recovery_never_finalizes_network_child_agent_run(monkeypatch) -> None:
    run = _run(network_execution_id=uuid4())
    _install_fake_uows(
        monkeypatch,
        [
            _ScalarResult(values=[run.id]),
            _ScalarResult(value=run),
        ],
    )
    worker = AgentRunRecoveryWorker(
        async_engine=MagicMock(),
        state_store=_StateStore(value=None),
        stale_after_seconds=60,
    )

    await worker.run()

    assert run.status == "running"
    assert run.completed_at is None
