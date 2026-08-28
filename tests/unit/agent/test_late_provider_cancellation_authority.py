from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
)
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _Outbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event) -> None:
        self.events.append(event)


class _Runs:
    def __init__(self, run: AgentRun) -> None:
        self.run = run
        self.save_calls = 0

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None

    async def get_by_id_for_update(self, run_id):
        return await self.get_by_id(run_id)

    async def save(self, run):
        self.run = run
        self.save_calls += 1
        return run


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.runs = _Runs(run)
        self.repositories = SimpleNamespace(runs=self.runs)
        self.outbox = _Outbox()

    async def run(self, operation):
        return await operation(self.repositories, self.outbox)

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


class _SwallowsFirstCancellationUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store
        self.started = asyncio.Event()
        self.cancelled_count = 0

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
        await self.store.create(
            self.run.id,
            {
                "status": "running",
                "project_id": str(self.run.project_id),
                "agent_id": str(self.run.agent_id),
            },
            ttl_seconds=3600,
        )
        await channel.emit(
            "meta",
            run_id=str(self.run.id),
            trace_id=str(self.run.trace_id),
            project_id=str(self.run.project_id),
            agent_id=str(self.run.agent_id),
        )
        self.started.set()

        while True:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled_count += 1
                if self.cancelled_count == 1:
                    # Simulates an upstream provider/library swallowing the first
                    # cancellation and attempting to continue the same invocation.
                    continue
                raise


class _LateSuccessUseCase:
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
        await self.store.create(
            self.run.id,
            {"status": "cancelled"},
            ttl_seconds=3600,
        )
        return SimpleNamespace(
            model_dump=lambda **_: {
                "run_id": str(self.run.id),
                "answer": "late success that must not win",
            }
        )


def _run(*, status: AgentRunStatus = AgentRunStatus.RUNNING) -> AgentRun:
    run = AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="cancel this",
        execution_snapshot={},
    )
    run.status = status
    if status != AgentRunStatus.RUNNING:
        run.result = {
            "answer": "",
            "cancelled": status == AgentRunStatus.CANCELLED,
            "partial": False,
        }
    return run


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
    )


async def _next_frame(stream, event_type: str) -> str:
    while True:
        frame = await asyncio.wait_for(anext(stream), timeout=2)
        if f"event: {event_type}" in frame:
            return frame


@pytest.mark.asyncio
async def test_cancellation_supervisor_reinterrupts_provider_that_swallows_first_cancel() -> None:
    run = _run()
    state = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _SwallowsFirstCancellationUseCase(run, state)
    service = AskAgentStreamService(use_case, transactions, state_store=state)

    stream = service.stream(_input(run))
    try:
        await _next_frame(stream, "meta")
        await asyncio.wait_for(use_case.started.wait(), timeout=1)
        await state.request_cancel(run.id)

        terminal = await _next_frame(stream, "cancelled")

        assert '"persisted": true' in terminal
        assert transactions.runs.run.status == AgentRunStatus.CANCELLED
        assert use_case.cancelled_count >= 2
        assert transactions.runs.run.result is not None
        assert transactions.runs.run.result["cancelled"] is True
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_late_success_is_projected_as_existing_durable_cancelled_terminal() -> None:
    run = _run(status=AgentRunStatus.CANCELLED)
    state = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        _LateSuccessUseCase(run, state),
        transactions,
        state_store=state,
    )
    channel = RuntimeStreamChannel()

    result = await service._run_execution(_input(run), channel)

    assert result.model_dump()["answer"] == "late success that must not win"
    terminal = await asyncio.wait_for(channel.queue.get(), timeout=1)
    assert terminal.event_type == "cancelled"
    assert terminal.payload["persisted"] is True
    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
