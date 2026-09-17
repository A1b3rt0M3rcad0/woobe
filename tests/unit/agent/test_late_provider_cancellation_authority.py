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


class _SwallowsCancellationUseCase:
    def __init__(
        self,
        run: AgentRun,
        store: InMemoryExecutionStateStore,
        *,
        swallow_count: int,
    ) -> None:
        self.run = run
        self.store = store
        self.swallow_count = swallow_count
        self.started = asyncio.Event()
        self.cancelled_count = 0
        self.stopped = asyncio.Event()

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
        await self.store.create(
            self.run.id,
            {
                "status": "running",
                "session_id": str(self.run.session_id),
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

        try:
            while True:
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    self.cancelled_count += 1
                    if self.cancelled_count <= self.swallow_count:
                        continue
                    raise
        finally:
            self.stopped.set()


class _LateSuccessUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store

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
        await self.store.create(
            self.run.id,
            {
                "status": self.run.status.value,
                "session_id": str(self.run.session_id),
            },
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
        session_id=uuid4(),
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


async def _wait_for_cancel_count(use_case: _SwallowsCancellationUseCase, count: int) -> None:
    for _ in range(200):
        if use_case.cancelled_count >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"expected at least {count} cancellation attempts, got {use_case.cancelled_count}")


@pytest.mark.asyncio
async def test_cancellation_supervisor_reinterrupts_provider_that_swallows_multiple_cancels() -> None:
    run = _run()
    state = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _SwallowsCancellationUseCase(run, state, swallow_count=3)
    service = AskAgentStreamService(use_case, transactions, state_store=state)

    stream = service.stream(_input(run))
    try:
        await _next_frame(stream, "meta")
        await asyncio.wait_for(use_case.started.wait(), timeout=1)
        await state.request_cancel(run.id)

        terminal = await _next_frame(stream, "cancelled")

        # The observer is released by the durable Run terminal, not by provider
        # cooperation. The provider may still be consuming repeated cancellation
        # attempts in the detached execution task at this point.
        assert '"persisted": true' in terminal
        assert transactions.runs.run.status == AgentRunStatus.CANCELLED
        assert transactions.runs.run.result is not None
        assert transactions.runs.run.result["cancelled"] is True

        await _wait_for_cancel_count(use_case, 4)
        await asyncio.wait_for(use_case.stopped.wait(), timeout=1)
        assert use_case.cancelled_count >= 4
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_uncertain"),
    [
        (AgentRunStatus.FAILED, False),
        (AgentRunStatus.UNCERTAIN, True),
    ],
)
async def test_late_success_projects_existing_durable_failure_terminal(
    status: AgentRunStatus,
    expected_uncertain: bool,
) -> None:
    run = _run(status=status)
    run.failure_detail = f"{status.value} terminal won first"
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
    assert terminal.event_type == "error"
    assert terminal.payload["status"] == status.value
    assert terminal.payload["uncertain"] is expected_uncertain
    assert "terminal won first" in str(terminal.payload["message"])
    assert transactions.runs.run.status == status
    assert channel.queue.empty()
