from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel


class _Outbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event) -> None:
        self.events.append(event)


class _RunRepository:
    def __init__(self, run: AgentRun) -> None:
        self.run = run
        self.save_calls = 0

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None

    async def save(self, run):
        self.run = run
        self.save_calls += 1
        return run


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.runs = _RunRepository(run)
        self.repositories = SimpleNamespace(runs=self.runs)
        self.outbox = _Outbox()
        self.write_calls = 0

    async def run(self, operation):
        self.write_calls += 1
        return await operation(self.repositories, self.outbox)


def _run() -> AgentRun:
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="cancel me",
        execution_snapshot={},
    )


def _channel(run: AgentRun) -> RuntimeStreamChannel:
    channel = RuntimeStreamChannel()
    channel.bind_execution(
        trace_id=run.trace_id,
        session_id=None,
        project_id=run.project_id,
        agent_id=run.agent_id,
    )
    setattr(channel, "run_id", run.id)
    return channel


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )


@pytest.mark.asyncio
async def test_stream_disconnect_terminalizes_running_agent_run() -> None:
    run = _run()
    transactions = _Transactions(run)
    service = AskAgentStreamService(SimpleNamespace(), transactions)

    persisted = await service._persist_cancelled(
        _channel(run),
        _input(run),
        "client_disconnected",
    )

    assert persisted is True
    assert transactions.write_calls == 1
    assert transactions.runs.save_calls == 1
    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    assert transactions.runs.run.failure_code == "cancelled"
    assert transactions.runs.run.failure_detail == "client_disconnected"
    assert transactions.runs.run.completed_at is not None
    assert transactions.runs.run.result is not None
    assert transactions.runs.run.result["run_id"] == str(run.id)
    assert len(transactions.outbox.events) == 1
    assert transactions.outbox.events[0].event_type == "agent.execution.cancelled.v1"


@pytest.mark.asyncio
async def test_late_stream_disconnect_does_not_overwrite_completed_run() -> None:
    run = _run()
    run.status = AgentRunStatus.COMPLETED
    transactions = _Transactions(run)
    service = AskAgentStreamService(SimpleNamespace(), transactions)

    persisted = await service._persist_cancelled(
        _channel(run),
        _input(run),
        "client_disconnected",
    )

    assert persisted is False
    assert transactions.runs.run.status == AgentRunStatus.COMPLETED
    assert transactions.runs.save_calls == 0
    assert transactions.outbox.events == []
