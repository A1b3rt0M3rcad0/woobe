from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel, current_runtime_stream
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _Runs:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(runs=_Runs(run))

    async def read(self, operation):
        return await operation(self.repositories, None)


class _LosingFinalizerUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store

    async def execute(self, _input_dto):
        channel = current_runtime_stream.get()
        assert channel is not None
        channel.bind_execution(
            trace_id=self.run.trace_id,
            session_id=None,
            project_id=self.run.project_id,
            agent_id=self.run.agent_id,
        )
        setattr(channel, "run_id", self.run.id)
        # Simulate the losing finalizer having published a transient pending state
        # immediately before PostgreSQL rejected its conflicting terminal UoW.
        await self.store.create(
            self.run.id,
            {
                "status": "terminal_pending_persist",
                "terminal_status": "completed",
                "terminal_result": {"answer": "late answer"},
            },
            ttl_seconds=3600,
        )
        raise RuntimeError("conflicting terminal writer rolled back")


def _run(status: AgentRunStatus) -> AgentRun:
    run = AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="race",
        execution_snapshot={},
    )
    run.status = status
    run.result = {
        "answer": "durable partial" if status == AgentRunStatus.CANCELLED else "",
        "partial": status == AgentRunStatus.CANCELLED,
        "cancelled": status == AgentRunStatus.CANCELLED,
    }
    if status in {AgentRunStatus.FAILED, AgentRunStatus.UNCERTAIN}:
        run.failure_detail = f"{status.value} won first"
    return run


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "event_type"),
    [
        (AgentRunStatus.CANCELLED, "cancelled"),
        (AgentRunStatus.FAILED, "error"),
        (AgentRunStatus.UNCERTAIN, "error"),
    ],
)
async def test_conflicting_terminal_exception_projects_and_restores_durable_winner(
    status: AgentRunStatus,
    event_type: str,
) -> None:
    run = _run(status)
    store = InMemoryExecutionStateStore()
    service = AskAgentStreamService(
        _LosingFinalizerUseCase(run, store),
        _Transactions(run),
        state_store=store,
    )
    channel = RuntimeStreamChannel()

    with pytest.raises(RuntimeError, match="conflicting terminal writer"):
        await service._run_execution(_input(run), channel)

    terminal = await channel.queue.get()
    assert terminal.event_type == event_type
    assert terminal.event_type != "done"
    if status == AgentRunStatus.CANCELLED:
        assert terminal.payload["output"] == "durable partial"
        assert terminal.payload["persisted"] is True
    else:
        assert terminal.payload["status"] == status.value
        assert terminal.payload["uncertain"] is (status == AgentRunStatus.UNCERTAIN)

    restored = await store.get(run.id)
    assert restored is not None
    assert restored["status"] == status.value
    assert restored["phase"] == "persisted"
    terminal_result = restored["terminal_result"]
    assert all(terminal_result[key] == value for key, value in run.result.items())
    if status == AgentRunStatus.CANCELLED:
        assert terminal_result["reason"] == "cancel_requested"
