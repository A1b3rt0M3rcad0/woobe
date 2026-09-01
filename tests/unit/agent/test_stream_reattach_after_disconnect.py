from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _Outbox:
    async def write(self, _event) -> None:
        return None


class _RunRepository:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None

    async def save(self, run):
        self.run = run
        return run


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(runs=_RunRepository(run))
        self.outbox = _Outbox()

    async def run(self, operation):
        return await operation(self.repositories, self.outbox)

    async def read(self, operation):
        return await operation(self.repositories, self.outbox)


class _ControlledUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store
        self.release = asyncio.Event()
        self.started = asyncio.Event()
        self.execute_calls = 0

    async def execute(self, input_dto):
        del input_dto
        self.execute_calls += 1
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
            content="partial",
            visibility="assistant",
            channel="final",
            phase="response_generation",
        )
        self.started.set()
        await self.release.wait()
        return SimpleNamespace(
            model_dump=lambda **_: {
                "run_id": str(self.run.id),
                "trace_id": str(self.run.trace_id),
                "answer": "partial complete",
            }
        )


class _UnavailableStore:
    async def get(self, _run_id):
        raise RuntimeError("hot state unavailable")


def _run() -> AgentRun:
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="keep the same logical run",
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


async def _wait_for_hot_token(store: InMemoryExecutionStateStore, run_id) -> None:
    for _ in range(100):
        events = await store.list_events_after(run_id, 0)
        if any(event.event_type == "token" for event in events):
            return
        await asyncio.sleep(0.01)
    raise AssertionError("token was not persisted to hot reattach state")


@pytest.mark.asyncio
async def test_transport_disconnect_then_reattach_continues_same_agent_run() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    use_case = _ControlledUseCase(run, store)
    service = AskAgentStreamService(use_case, _Transactions(run), state_store=store)

    initial = service.stream(_input(run))
    assert str(run.id) in await _next_frame(initial, "meta")
    assert '\"content\": \"partial\"' in await _next_frame(initial, "token")
    await asyncio.wait_for(use_case.started.wait(), timeout=1)
    await _wait_for_hot_token(store, run.id)

    await initial.aclose()

    reattached = service.attach(run.id)
    state = await _next_frame(reattached, "run.state")
    assert '\"run_id\": \"' + str(run.id) + '\"' in state
    assert '\"output\": \"partial\"' in state
    assert use_case.execute_calls == 1

    use_case.release.set()
    terminal = await _next_frame(reattached, "done")
    assert '\"answer\": \"partial complete\"' in terminal
    assert use_case.execute_calls == 1

    await reattached.aclose()


@pytest.mark.asyncio
async def test_two_observers_share_one_active_agent_run_and_both_receive_terminal_state() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    use_case = _ControlledUseCase(run, store)
    service = AskAgentStreamService(use_case, _Transactions(run), state_store=store)

    initial = service.stream(_input(run))
    await _next_frame(initial, "meta")
    await _next_frame(initial, "token")
    await _wait_for_hot_token(store, run.id)

    reattached = service.attach(run.id)
    state = await _next_frame(reattached, "run.state")
    assert '\"output\": \"partial\"' in state
    assert use_case.execute_calls == 1

    use_case.release.set()

    initial_terminal = await _next_frame(initial, "done")
    reattached_terminal = await _next_frame(reattached, "done")
    assert '\"answer\": \"partial complete\"' in initial_terminal
    assert '\"answer\": \"partial complete\"' in reattached_terminal
    assert use_case.execute_calls == 1

    await initial.aclose()
    await reattached.aclose()


@pytest.mark.asyncio
async def test_second_observer_can_cancel_same_run_and_both_receive_cancelled_terminal() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    use_case = _ControlledUseCase(run, store)
    transactions = _Transactions(run)
    service = AskAgentStreamService(use_case, transactions, state_store=store)

    initial = service.stream(_input(run))
    await _next_frame(initial, "meta")
    await _next_frame(initial, "token")
    await _wait_for_hot_token(store, run.id)

    reattached = service.attach(run.id)
    state = await _next_frame(reattached, "run.state")
    assert '\"output\": \"partial\"' in state
    assert use_case.execute_calls == 1

    # Models a second client issuing POST /runs/{id}/cancel while the first client
    # remains attached to the original POST stream. Cancellation belongs to the Run,
    # so both observers must converge on the same durable terminal fact.
    await store.request_cancel(run.id)

    initial_terminal = await _next_frame(initial, "cancelled")
    reattached_terminal = await _next_frame(reattached, "cancelled")

    assert '\"persisted\": true' in initial_terminal
    assert '\"output\": \"partial\"' in initial_terminal
    assert '\"output\": \"partial\"' in reattached_terminal
    assert transactions.repositories.runs.run.status == AgentRunStatus.CANCELLED
    assert use_case.execute_calls == 1

    await initial.aclose()
    await reattached.aclose()


@pytest.mark.asyncio
async def test_terminal_cancelled_run_reattaches_from_durable_state_when_hot_state_is_unavailable() -> None:
    run = _run()
    run.status = AgentRunStatus.CANCELLED
    run.result = {
        "answer": "durable partial",
        "partial": True,
        "cancelled": True,
        "reason": "cancel_requested",
    }
    transactions = _Transactions(run)
    service = AskAgentStreamService(
        SimpleNamespace(),
        transactions,
        state_store=_UnavailableStore(),
    )

    reattached = service.attach(run.id)
    state = await _next_frame(reattached, "run.state")

    assert '\"status\": \"cancelled\"' in state
    assert '\"output\": \"durable partial\"' in state
    assert '\"realtime_available\": false' in state

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(reattached), timeout=1)
