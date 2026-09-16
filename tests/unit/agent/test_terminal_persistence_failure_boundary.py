from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.run import AgentRun
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel, current_runtime_stream
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _PersistenceFailureTransactions:
    async def run(self, _operation):
        raise RuntimeError("postgres terminal persistence unavailable")

    async def read(self, _operation):
        return None


class _CancelledUseCase:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def execute(self, _input_dto):
        channel = current_runtime_stream.get()
        assert channel is not None
        channel.bind_execution(
            trace_id=self.run.trace_id,
            session_id=self.run.session_id,
            project_id=self.run.project_id,
            agent_id=self.run.agent_id,
        )
        setattr(channel, "run_id", self.run.id)
        raise asyncio.CancelledError


def _run() -> AgentRun:
    return AgentRun(
        session_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="cancel",
        execution_snapshot={},
    )


@pytest.mark.asyncio
async def test_postgres_terminal_failure_never_emits_false_durable_cancelled_event() -> None:
    run = _run()
    service = AskAgentStreamService(
        _CancelledUseCase(run),
        _PersistenceFailureTransactions(),
        state_store=InMemoryExecutionStateStore(),
    )
    channel = RuntimeStreamChannel()
    input_dto = AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )

    with pytest.raises(RuntimeError, match="postgres terminal persistence unavailable"):
        await service._run_execution(input_dto, channel)

    queued = []
    while not channel.queue.empty():
        queued.append(channel.queue.get_nowait())

    assert all(event.event_type != "cancelled" for event in queued)
    assert all(event.payload.get("persisted") is not True for event in queued)
