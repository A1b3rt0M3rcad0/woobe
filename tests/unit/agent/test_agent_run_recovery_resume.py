from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.agent.application.execution_strategy_config import (
    execution_strategy_from_runtime_config,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.agent_run_recovery_runtime import (
    AgentRunRecoveryExecutor,
    AgentRunRecoveryRequest,
    AgentRunRecoveryRuntime,
)
from shared.contracts.execution_state import ExecutionLease
from shared.contracts.run_event_journal import RunCheckpoint, RunJournalState
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION
from woobe_workers.consumers.agent.run_recovery_worker import (
    AgentRunRecoveryWorker,
    _JournalRecoveryDecision,
    _RecoveryRunRecord,
)


class _CapturingRuntime:
    def __init__(self) -> None:
        self.context = None
        self.input_dto = None

    async def execute(self, input_dto):
        self.context = deepcopy(current_execution.get())
        self.input_dto = input_dto
        return "completed"


class _RecoveryStateStore:
    def __init__(self) -> None:
        self.created = []
        self.leases = []

    async def create(self, run_id, state, *, ttl_seconds):
        self.created.append((run_id, dict(state), ttl_seconds))

    async def acquire_lease(self, run_id, *, worker_id, ttl_seconds):
        self.leases.append((run_id, worker_id, ttl_seconds))
        return ExecutionLease(owner=worker_id, generation=1)


class _RecoveryBuffer:
    def __init__(self) -> None:
        self.reconciled = []

    async def ensure_sequence_at_least(self, run_id, sequence):
        self.reconciled.append((run_id, sequence))
        return sequence


def test_recovery_rehydrates_execution_strategy_from_accepted_snapshot() -> None:
    agent_id = uuid4()
    run = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        agent_id=agent_id,
        session_id=None,
        input_message_id=None,
        trace_id=uuid4(),
        agent_release_id=None,
        environment="draft",
        input_message="continue",
        execution_snapshot={
            "agent": {
                "id": str(agent_id),
                "provider": "openai",
                "model": "snapshot-model",
                "session_mode": "stateless",
                "settings": {
                    "runtime_config": {
                        "execution_strategy": "standard",
                    }
                },
            }
        },
    )
    live_agent = SimpleNamespace(
        settings={"runtime_config": {"execution_strategy": "react"}},
    )
    context = SimpleNamespace(
        tool_snapshots=None,
        agent_release_version=None,
    )

    accepted = AgentRunRecoveryRuntime._accepted_snapshot(run)
    recovered = AgentRunRecoveryRuntime._apply_accepted_snapshot(
        live_agent,
        accepted,
        context,
    )

    runtime_config = recovered.settings["runtime_config"]
    assert runtime_config == {"execution_strategy": "standard"}
    assert execution_strategy_from_runtime_config(runtime_config) == "standard"
    assert recovered.model == "snapshot-model"


@pytest.mark.asyncio
async def test_recovery_executor_preserves_same_run_identity_and_injects_checkpoint() -> None:
    runtime = _CapturingRuntime()
    executor = AgentRunRecoveryExecutor(runtime)  # type: ignore[arg-type]
    run_id = uuid4()
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    message_id = uuid4()
    trace_id = uuid4()
    release_id = uuid4()
    checkpoint = {
        "kind": "agent_execution",
        "next_phase": "model_invocation",
        "capability_messages": [{"role": "assistant", "content": "tool result"}],
    }

    result = await executor.execute(
        AgentRunRecoveryRequest(
            run_id=run_id,
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            input_message_id=message_id,
            trace_id=trace_id,
            agent_release_id=release_id,
            environment="production",
            input_message="continue",
            attempt=2,
            checkpoint=checkpoint,
        )
    )

    assert result == "completed"
    assert runtime.context is not None
    assert runtime.context.run_id == run_id
    assert runtime.context.trace_id == trace_id
    assert runtime.context.input_message_id == message_id
    assert runtime.context.agent_release_id == release_id
    assert runtime.context.storage_version == EVENT_JOURNAL_STORAGE_VERSION
    assert runtime.context.run_attempt == 2
    assert runtime.context.resume_state == checkpoint
    assert runtime.context.resume_state is not checkpoint
    assert runtime.input_dto.metadata["source"] == "run_recovery"
    assert runtime.input_dto.project_id == project_id
    assert runtime.input_dto.agent_id == agent_id
    assert runtime.input_dto.session_id == session_id
    assert runtime.input_dto.loaded_release_id == release_id


@pytest.mark.asyncio
async def test_recovery_worker_resumes_same_run_with_next_attempt_after_sequence_reconcile() -> None:
    state_store = _RecoveryStateStore()
    buffer = _RecoveryBuffer()
    captured = []

    async def resume(request: AgentRunRecoveryRequest):
        captured.append(request)

    worker = AgentRunRecoveryWorker(
        async_engine=MagicMock(),
        state_store=state_store,  # type: ignore[arg-type]
        stale_after_seconds=900,
        journal=MagicMock(),
        buffer=buffer,  # type: ignore[arg-type]
        barrier=MagicMock(),
        resume_run=resume,
    )
    run = _RecoveryRunRecord(
        id=uuid4(),
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        project_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        input_message_id=uuid4(),
        trace_id=uuid4(),
        agent_release_id=uuid4(),
        environment="production",
        input_message="original input",
    )
    state = RunJournalState(
        run_id=run.id,
        run_kind="agent",
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        durable_sequence=17,
    )
    checkpoint_state = {
        "kind": "agent_execution",
        "next_phase": "model_invocation",
        "capability_messages": [],
    }
    checkpoint = RunCheckpoint(
        run_id=run.id,
        through_sequence=16,
        attempt=3,
        state=checkpoint_state,
        updated_at="2026-09-10T00:00:00+00:00",
    )

    await worker._resume_journal_run(
        run,
        state=state,
        decision=_JournalRecoveryDecision(
            action="resumable",
            checkpoint=checkpoint,
            attempt=3,
        ),
    )

    assert buffer.reconciled == [(run.id, 17)]
    assert len(captured) == 1
    request = captured[0]
    assert request.run_id == run.id
    assert request.trace_id == run.trace_id
    assert request.input_message_id == run.input_message_id
    assert request.agent_release_id == run.agent_release_id
    assert request.attempt == 4
    assert request.checkpoint == checkpoint_state
    assert request.checkpoint is not checkpoint_state
    assert state_store.created[0][1]["status"] == "recovering"
    assert state_store.created[0][1]["attempt"] == 4
    assert len(state_store.leases) == 1
