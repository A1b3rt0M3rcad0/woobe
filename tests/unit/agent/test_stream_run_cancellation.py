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

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


class _DetachedUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store
        self.completed = asyncio.Event()

    async def execute(self, input_dto):
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
        await self.store.append_event(
            self.run.id,
            "agent.run.accepted",
            {"trace_id": str(self.run.trace_id)},
        )
        await channel.emit(
            "meta",
            run_id=str(self.run.id),
            trace_id=str(self.run.trace_id),
            project_id=str(self.run.project_id),
            agent_id=str(self.run.agent_id),
        )
        await channel.emit(
            "token",
            content="partial",
            visibility="assistant",
            channel="final",
            phase="response_generation",
        )
        await asyncio.sleep(0.05)
        self.completed.set()
        return SimpleNamespace(
            model_dump=lambda **_: {
                "run_id": str(self.run.id),
                "answer": "completed after observer left",
            }
        )


class _BlockingCancelableUseCase:
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
            "token",
            content="partial before stop",
            visibility="assistant",
            channel="final",
            phase="response_generation",
        )
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class _CancelledRaceUseCase:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

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
        raise asyncio.CancelledError


class _NoInitialTailReadStore(InMemoryExecutionStateStore):
    async def read_events_after_cursor(self, *args, **kwargs):
        raise AssertionError("initial POST observer must not consume the Redis/hot tail")


class _BlockingTokenPersistenceStore(InMemoryExecutionStateStore):
    def __init__(self) -> None:
        super().__init__()
        self.token_persist_started = asyncio.Event()
        self.release_token_persist = asyncio.Event()

    async def append_event(
        self,
        run_id,
        event_type,
        payload,
        *,
        maxlen=2000,
    ):
        if event_type == "token":
            self.token_persist_started.set()
            await self.release_token_persist.wait()
        return await super().append_event(
            run_id,
            event_type,
            payload,
            maxlen=maxlen,
        )


def _run() -> AgentRun:
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="keep running",
        execution_snapshot={},
    )


def _input(run: AgentRun) -> AskInput:
    return AskInput(
        project_id=run.project_id,
        agent_id=run.agent_id,
        message=run.input_message,
        execution_context="playground",
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


@pytest.mark.asyncio
async def test_closing_stream_observer_does_not_cancel_agent_execution() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _DetachedUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    first = await anext(stream)
    assert "event: meta" in first
    assert str(run.id) in first

    await stream.aclose()
    await asyncio.wait_for(use_case.completed.wait(), timeout=1)

    assert transactions.write_calls == 0
    assert transactions.runs.run.status == AgentRunStatus.RUNNING


@pytest.mark.asyncio
async def test_initial_post_observer_receives_live_token_without_hot_tail_read() -> None:
    run = _run()
    store = _NoInitialTailReadStore()
    transactions = _Transactions(run)
    use_case = _DetachedUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    first = await asyncio.wait_for(anext(stream), timeout=1)
    second = await asyncio.wait_for(anext(stream), timeout=1)

    assert "event: meta" in first
    assert "event: token" in second
    assert '"content": "partial"' in second
    assert use_case.completed.is_set() is False

    await stream.aclose()
    await asyncio.wait_for(use_case.completed.wait(), timeout=1)


@pytest.mark.asyncio
async def test_initial_post_token_is_visible_before_hot_persistence_completes() -> None:
    run = _run()
    store = _BlockingTokenPersistenceStore()
    transactions = _Transactions(run)
    use_case = _DetachedUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    try:
        first = await asyncio.wait_for(anext(stream), timeout=1)
        second = await asyncio.wait_for(anext(stream), timeout=1)

        assert "event: meta" in first
        assert "event: token" in second
        assert '"content": "partial"' in second
        await asyncio.wait_for(store.token_persist_started.wait(), timeout=1)
        assert store.release_token_persist.is_set() is False
    finally:
        store.release_token_persist.set()
        await stream.aclose()

    await asyncio.wait_for(use_case.completed.wait(), timeout=1)


@pytest.mark.asyncio
async def test_cancel_watcher_is_not_blocked_by_hot_event_persistence() -> None:
    run = _run()
    store = _BlockingTokenPersistenceStore()
    transactions = _Transactions(run)
    use_case = _BlockingCancelableUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    try:
        first = await asyncio.wait_for(anext(stream), timeout=1)
        second = await asyncio.wait_for(anext(stream), timeout=1)
        assert "event: meta" in first
        assert "event: token" in second
        await asyncio.wait_for(store.token_persist_started.wait(), timeout=1)
        assert store.release_token_persist.is_set() is False

        await store.request_cancel(run.id)

        terminal = await asyncio.wait_for(anext(stream), timeout=1)
        assert "event: cancelled" in terminal
        assert '"persisted": true' in terminal
        assert store.release_token_persist.is_set() is False
        await asyncio.wait_for(use_case.cancelled.wait(), timeout=1)
        assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    finally:
        store.release_token_persist.set()
        await stream.aclose()


@pytest.mark.asyncio
async def test_cancel_request_drives_task_cancellation_persistence_and_terminal_event() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _BlockingCancelableUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    stream = service.stream(_input(run))
    first = await asyncio.wait_for(anext(stream), timeout=1)
    second = await asyncio.wait_for(anext(stream), timeout=1)
    assert "event: meta" in first
    assert "event: token" in second
    await asyncio.wait_for(use_case.started.wait(), timeout=1)

    await store.request_cancel(run.id)

    terminal = await asyncio.wait_for(anext(stream), timeout=2)
    assert "event: cancelled" in terminal
    assert '"output": "partial before stop"' in terminal
    assert '"persisted": true' in terminal
    await asyncio.wait_for(use_case.cancelled.wait(), timeout=1)

    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    assert transactions.runs.run.result is not None
    assert transactions.runs.run.result["answer"] == "partial before stop"
    assert transactions.runs.run.result["partial"] is True
    assert transactions.runs.run.result["cancelled"] is True
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=1)


@pytest.mark.asyncio
async def test_explicit_cancellation_still_terminalizes_running_agent_run() -> None:
    run = _run()
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = _channel(run)
    channel.public_output = "partial answer"
    channel.latest_usage = {
        "input_tokens": 11,
        "output_tokens": 7,
        "total_tokens": 18,
    }

    persisted = await service._persist_cancelled(
        channel,
        _input(run),
        "cancel_requested",
    )

    assert persisted is True
    assert transactions.write_calls == 1
    assert transactions.runs.save_calls == 1
    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    assert transactions.runs.run.failure_code is None
    assert transactions.runs.run.failure_detail is None
    assert transactions.runs.run.result is not None
    assert transactions.runs.run.result["answer"] == "partial answer"
    assert transactions.runs.run.result["partial"] is True
    assert transactions.runs.run.result["cancelled"] is True
    assert transactions.runs.run.result["reason"] == "cancel_requested"
    assert transactions.runs.run.usage == channel.latest_usage
    assert transactions.runs.run.completed_at is not None


@pytest.mark.asyncio
async def test_explicit_cancellation_before_first_token_is_not_a_failure() -> None:
    run = _run()
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = _channel(run)

    assert channel.public_output == ""
    assert channel.latest_usage is None

    persisted = await service._persist_cancelled(
        channel,
        _input(run),
        "cancel_requested",
    )

    assert persisted is True
    assert transactions.runs.run.status == AgentRunStatus.CANCELLED
    assert transactions.runs.run.failure_code is None
    assert transactions.runs.run.failure_detail is None
    assert transactions.runs.run.result is not None
    assert transactions.runs.run.result["answer"] == ""
    assert transactions.runs.run.result["partial"] is False
    assert transactions.runs.run.result["cancelled"] is True
    assert transactions.runs.run.result["reason"] == "cancel_requested"
    assert transactions.runs.run.result["usage"] is None
    assert transactions.runs.run.completed_at is not None


@pytest.mark.asyncio
async def test_late_explicit_cancel_does_not_overwrite_completed_run() -> None:
    run = _run()
    run.status = AgentRunStatus.COMPLETED
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = _channel(run)

    persisted = await service._persist_cancelled(
        channel,
        _input(run),
        "cancel_requested",
    )

    assert persisted is False
    assert transactions.runs.run.status == AgentRunStatus.COMPLETED
    assert transactions.runs.save_calls == 0
    assert transactions.outbox.events == []


@pytest.mark.asyncio
async def test_cancel_completion_race_emits_durable_completed_terminal_instead_of_false_cancelled() -> None:
    run = _run()
    run.status = AgentRunStatus.COMPLETED
    run.result = {
        "answer": "durable winner",
        "trace_id": str(run.trace_id),
        "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5},
    }
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        _CancelledRaceUseCase(run),
        transactions,
        state_store=InMemoryExecutionStateStore(),
    )
    channel = _channel(run)

    with pytest.raises(asyncio.CancelledError):
        await service._run_execution(_input(run), channel)

    terminal = await asyncio.wait_for(channel.queue.get(), timeout=1)
    assert terminal.event_type == "done"
    assert terminal.payload["answer"] == "durable winner"
    assert terminal.payload.get("cancelled") is not True
    assert transactions.runs.run.status == AgentRunStatus.COMPLETED
    assert transactions.runs.save_calls == 0
