from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from shared.contracts.run_event_buffer import RunEventAppendReceipt
from shared.contracts.run_event_journal import DurableRunEvent, RunCheckpoint, RunJournalState
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
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
        self.created: list[tuple[object, dict, int]] = []
        self.updated: list[tuple[object, dict]] = []
        self.expired: list[tuple[object, int]] = []
        self.lease_granted = True

    async def get(self, run_id):
        self.reads.append(run_id)
        if self.error is not None:
            raise self.error
        return self.value

    async def create(self, run_id, state, *, ttl_seconds):
        self.created.append((run_id, dict(state), ttl_seconds))

    async def acquire_lease(self, run_id, *, worker_id, ttl_seconds):
        del run_id, worker_id, ttl_seconds
        return SimpleNamespace(owner="worker", generation=1) if self.lease_granted else None

    async def update(self, run_id, values):
        self.updated.append((run_id, dict(values)))

    async def expire(self, run_id, *, ttl_seconds):
        self.expired.append((run_id, ttl_seconds))


def _run(*, network_execution_id=None, storage_version="legacy_v1"):
    return SimpleNamespace(
        id=uuid4(),
        status="running",
        storage_version=storage_version,
        network_execution_id=network_execution_id,
        started_at=datetime.now(timezone.utc) - timedelta(hours=2),
        trace_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        input_message_id=uuid4(),
        agent_release_id=None,
        environment="development",
        input_message="recover me",
        failure_code=None,
        failure_detail=None,
        result=None,
        completed_at=None,
    )


def _event(run_id, sequence, event_type, payload, *, attempt=1):
    return DurableRunEvent(
        run_id=run_id,
        run_kind="agent",
        sequence=sequence,
        event_id=str(uuid4()),
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={"attempt": attempt},
        payload=dict(payload),
    )


class _Journal:
    def __init__(self, *, state, events=None, checkpoint=None) -> None:
        self.state = state
        self.events = list(events or [])
        self.checkpoint = checkpoint

    async def get_state(self, _run_id):
        return self.state

    async def list_events(self, _run_id, **_kwargs):
        return list(self.events)

    async def latest_checkpoint(self, _run_id):
        return self.checkpoint


class _Buffer:
    def __init__(self, *, starting_sequence=0) -> None:
        self.sequence = starting_sequence
        self.reconciled: list[int] = []
        self.appended: list[tuple[str, dict]] = []

    async def ensure_sequence_at_least(self, _run_id, sequence):
        self.sequence = max(self.sequence, int(sequence))
        self.reconciled.append(int(sequence))
        return self.sequence

    async def append(self, *, run_id, event_type, payload, **_kwargs):
        self.sequence += 1
        self.appended.append((event_type, dict(payload)))
        return RunEventAppendReceipt(
            run_id=run_id,
            sequence=self.sequence,
            cursor=f"{self.sequence}-0",
            occurred_at=datetime.now(timezone.utc).isoformat(),
        )


class _Barrier:
    def __init__(self) -> None:
        self.waits: list[int] = []

    async def wait_until(self, _run_id, sequence):
        self.waits.append(sequence)


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
async def test_event_journal_unknown_tool_outcome_becomes_journal_uncertain(monkeypatch) -> None:
    run = _run(storage_version=EVENT_JOURNAL_STORAGE_VERSION)
    state = RunJournalState(
        run_id=run.id,
        run_kind="agent",
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        durable_sequence=3,
    )
    journal = _Journal(
        state=state,
        events=[
            _event(run.id, 1, "run.attempt.started", {"attempt": 1}),
            _event(
                run.id,
                2,
                "tool.call.started",
                {"operation_id": "tool-1", "external_outcome": "pending"},
            ),
            _event(
                run.id,
                3,
                "model.invocation.started",
                {"operation_id": "model-2"},
            ),
        ],
    )
    buffer = _Buffer()
    barrier = _Barrier()
    store = _StateStore(value=None)
    _install_fake_uows(
        monkeypatch,
        [_ScalarResult(values=[run.id]), _ScalarResult(value=run)],
    )

    worker = AgentRunRecoveryWorker(
        async_engine=MagicMock(),
        state_store=store,
        stale_after_seconds=60,
        journal=journal,
        buffer=buffer,
        barrier=barrier,
    )
    await worker.run()

    assert buffer.reconciled == [3]
    assert buffer.appended[-1][0] == "run.uncertain"
    assert buffer.appended[-1][1]["failure_code"] == "unsafe_recovery_boundary"
    assert "tool_started_without_known_outcome" in buffer.appended[-1][1]["recovery_reason"]
    assert barrier.waits == [4]
    assert store.updated[-1][1]["status"] == "uncertain"


@pytest.mark.asyncio
async def test_event_journal_completed_tool_requires_checkpoint_after_result() -> None:
    run = _run(storage_version=EVENT_JOURNAL_STORAGE_VERSION)
    state = RunJournalState(
        run_id=run.id,
        run_kind="agent",
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        durable_sequence=3,
    )
    events = [
        _event(run.id, 1, "tool.call.started", {"operation_id": "tool-1"}),
        _event(
            run.id,
            2,
            "tool.call.completed",
            {"operation_id": "tool-1", "external_outcome": "known"},
        ),
        _event(run.id, 3, "model.invocation.started", {"operation_id": "model-2"}),
    ]
    checkpoint = RunCheckpoint(
        run_id=run.id,
        through_sequence=1,
        attempt=1,
        state={"next_phase": "tool_followup_1"},
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    decision = AgentRunRecoveryWorker._classify_journal_prefix(
        state,
        events,
        checkpoint,
    )

    assert decision.action == "uncertain"
    assert decision.reason == "tool_result_without_causal_checkpoint:2>1"


@pytest.mark.asyncio
async def test_event_journal_tool_checkpoint_is_resumable() -> None:
    run = _run(storage_version=EVENT_JOURNAL_STORAGE_VERSION)
    state = RunJournalState(
        run_id=run.id,
        run_kind="agent",
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        durable_sequence=3,
    )
    events = [
        _event(run.id, 1, "tool.call.started", {"operation_id": "tool-1"}),
        _event(
            run.id,
            2,
            "tool.call.completed",
            {"operation_id": "tool-1", "external_outcome": "known"},
        ),
        _event(run.id, 3, "execution.checkpoint", {"attempt": 1}),
    ]
    checkpoint = RunCheckpoint(
        run_id=run.id,
        through_sequence=3,
        attempt=1,
        state={"next_phase": "tool_followup_1"},
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    decision = AgentRunRecoveryWorker._classify_journal_prefix(
        state,
        events,
        checkpoint,
    )

    assert decision.action == "resumable"
    assert decision.checkpoint is checkpoint


@pytest.mark.asyncio
async def test_context_checkpoint_is_merged_into_safe_execution_checkpoint() -> None:
    run = _run(storage_version=EVENT_JOURNAL_STORAGE_VERSION)
    state = RunJournalState(
        run_id=run.id,
        run_kind="agent",
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        durable_sequence=5,
    )
    events = [
        _event(run.id, 1, "tool.call.started", {"operation_id": "tool-1"}),
        _event(
            run.id,
            2,
            "tool.call.completed",
            {"operation_id": "tool-1", "external_outcome": "known"},
        ),
        _event(run.id, 3, "execution.checkpoint", {"attempt": 1}),
        _event(
            run.id,
            4,
            "context.checkpoint",
            {
                "manager_name": "adaptive",
                "boundary": "context_summary_boundary",
                "state": {
                    "summaries": {"SESSION": {"summary_ref": "summary-1"}},
                    "summary_generation": 1,
                },
            },
        ),
        _event(run.id, 5, "model.invocation.started", {"operation_id": "model-2"}),
    ]
    checkpoint = RunCheckpoint(
        run_id=run.id,
        through_sequence=3,
        attempt=1,
        state={
            "phase": "agent_tool_boundary",
            "resume_policy": "continue_execution_strategy",
            "execution_strategy": "standard",
            "strategy_cursor": {"state": {"phase": "tool_followup_1"}},
        },
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    decision = AgentRunRecoveryWorker._classify_journal_prefix(
        state,
        events,
        checkpoint,
    )

    assert decision.action == "resumable"
    assert decision.checkpoint is not None
    assert decision.checkpoint.through_sequence == 3
    assert decision.checkpoint.state["context_manager_state"] == {
        "manager_name": "adaptive",
        "boundary": "context_summary_boundary",
        "state": {
            "summaries": {"SESSION": {"summary_ref": "summary-1"}},
            "summary_generation": 1,
        },
    }


@pytest.mark.asyncio
async def test_execution_checkpoint_keeps_newer_embedded_context_state() -> None:
    run = _run(storage_version=EVENT_JOURNAL_STORAGE_VERSION)
    state = RunJournalState(
        run_id=run.id,
        run_kind="agent",
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        durable_sequence=4,
    )
    events = [
        _event(
            run.id,
            2,
            "context.checkpoint",
            {
                "manager_name": "adaptive",
                "boundary": "context_summary_boundary",
                "state": {"summary_generation": 1},
            },
        ),
        _event(run.id, 4, "execution.checkpoint", {"attempt": 1}),
    ]
    checkpoint = RunCheckpoint(
        run_id=run.id,
        through_sequence=4,
        attempt=1,
        state={
            "context_manager_state": {
                "manager_name": "adaptive",
                "boundary": "context_summary_boundary",
                "state": {"summary_generation": 2},
            }
        },
        updated_at=datetime.now(timezone.utc).isoformat(),
    )

    decision = AgentRunRecoveryWorker._classify_journal_prefix(
        state,
        events,
        checkpoint,
    )

    assert decision.action == "resumable"
    assert decision.checkpoint is not None
    assert decision.checkpoint.state["context_manager_state"]["state"] == {
        "summary_generation": 2
    }


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
