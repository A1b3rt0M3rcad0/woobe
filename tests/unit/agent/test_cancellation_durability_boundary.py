from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.run import AgentRun
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import RuntimeStreamChannel
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _CancelledUseCase:
    async def execute(self, _input):
        raise asyncio.CancelledError


class _FailingTransactions:
    async def run(self, _operation):
        raise RuntimeError("postgres finalization failed")

    async def read(self, _operation):
        raise AssertionError("read is not expected")


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


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )


@pytest.mark.asyncio
async def test_agent_cancellation_does_not_emit_false_terminal_when_postgres_finalization_fails() -> None:
    run = _run()
    channel = RuntimeStreamChannel()
    channel.bind_execution(
        trace_id=run.trace_id,
        session_id=run.session_id,
        project_id=run.project_id,
        agent_id=run.agent_id,
    )
    setattr(channel, "run_id", run.id)
    service = AskAgentStreamService(
        _CancelledUseCase(),
        _FailingTransactions(),
        state_store=InMemoryExecutionStateStore(),
    )

    with pytest.raises(RuntimeError, match="postgres finalization failed"):
        await service._run_execution(_input(run), channel)

    queued = []
    while not channel.queue.empty():
        queued.append(channel.queue.get_nowait().event_type)

    assert "cancelled" not in queued
    assert channel.terminal_emitted is False
