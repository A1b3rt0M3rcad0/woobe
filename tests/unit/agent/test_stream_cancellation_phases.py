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
    invoke_model_with_optional_streaming,
)
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


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

    async def run(self, operation):
        return await operation(self.repositories, self.outbox)

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


class _Chunk:
    def __init__(self, content: str = "") -> None:
        self.content = content
        self.tool_calls = []
        self.tool_call_chunks = []

    def __add__(self, other: "_Chunk") -> "_Chunk":
        return _Chunk(self.content + other.content)


class _BlockingStreamModel:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def astream(self, _messages):
        yield _Chunk("partial phase output")
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class _PhaseUseCase:
    def __init__(
        self,
        run: AgentRun,
        store: InMemoryExecutionStateStore,
        *,
        phase: str,
    ) -> None:
        self.run = run
        self.store = store
        self.phase = phase
        self.model = _BlockingStreamModel()

    async def execute(self, input_dto):
        del input_dto
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
        await invoke_model_with_optional_streaming(
            model=self.model,
            messages=[],
            phase=self.phase,
            provider="test-provider",
            model_name="test-model",
        )
        raise AssertionError("blocking provider should not complete after cancellation")


class _BlockingToolUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def execute(self, input_dto):
        del input_dto
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
        await channel.emit(
            "tool_call_started",
            tool_call_id="tool-call-1",
            tool_name="external_capability",
        )
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class _CancelledRaceUseCase:
    async def execute(self, _input_dto):
        raise asyncio.CancelledError


def _run() -> AgentRun:
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="cancel this run",
        execution_snapshot={},
    )


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
@pytest.mark.parametrize(
    ("phase", "expects_partial"),
    [
        ("capability_response_generation", True),
        ("tool_followup_1", True),
        ("final_response_generation", True),
        ("json_repair", False),
    ],
)
async def test_cancel_interrupts_active_model_phase_and_durably_terminalizes_run(
    phase: str,
    expects_partial: bool,
) -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _PhaseUseCase(run, store, phase=phase)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    try:
        meta = await _next_frame(stream, "meta")
        assert str(run.id) in meta
        await asyncio.wait_for(use_case.model.started.wait(), timeout=1)

        await store.request_cancel(run.id)
        terminal = await _next_frame(stream, "cancelled")

        assert '"persisted": true' in terminal
        await asyncio.wait_for(use_case.model.cancelled.wait(), timeout=1)
        assert transactions.runs.run.status == AgentRunStatus.CANCELLED
        assert transactions.runs.run.result is not None
        assert transactions.runs.run.result["cancelled"] is True
        assert transactions.runs.run.result["partial"] is expects_partial
        expected_output = "partial phase output" if expects_partial else ""
        assert transactions.runs.run.result["answer"] == expected_output
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_cancel_interrupts_active_tool_boundary_without_marking_run_failed() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _BlockingToolUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    try:
        await _next_frame(stream, "meta")
        await asyncio.wait_for(use_case.started.wait(), timeout=1)

        await store.request_cancel(run.id)
        terminal = await _next_frame(stream, "cancelled")

        assert '"persisted": true' in terminal
        await asyncio.wait_for(use_case.cancelled.wait(), timeout=1)
        assert transactions.runs.run.status == AgentRunStatus.CANCELLED
        assert transactions.runs.run.failure_code is None
        assert transactions.runs.run.failure_detail is None
    finally:
        await stream.aclose()


@pytest.mark.asyncio
async def test_cancel_failure_race_keeps_durable_failure_as_authoritative_winner() -> None:
    run = _run()
    run.status = AgentRunStatus.FAILED
    run.failure_code = "provider_request_error"
    run.failure_detail = "provider failed first"
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        _CancelledRaceUseCase(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )

    runtime_channel = RuntimeStreamChannel()
    runtime_channel.bind_execution(
        trace_id=run.trace_id,
        session_id=None,
        project_id=run.project_id,
        agent_id=run.agent_id,
    )
    setattr(runtime_channel, "run_id", run.id)

    with pytest.raises(asyncio.CancelledError):
        await service._run_execution(_input(run), runtime_channel)

    terminal = await asyncio.wait_for(runtime_channel.queue.get(), timeout=1)
    assert terminal.event_type == "error"
    assert "provider failed first" in str(terminal.payload.get("message"))
    assert transactions.runs.run.status == AgentRunStatus.FAILED
    assert transactions.runs.save_calls == 0
