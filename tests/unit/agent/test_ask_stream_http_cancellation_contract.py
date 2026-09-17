from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.agent_run_reattach_service import AgentRunReattachService
from modules.agent.infra.execution.ask_agent_stream_service import AskAgentStreamService
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream
from woobe_api.http.agent.controllers.ask_agent_stream_controller import handle_ask_stream
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.security.principal import ProjectApiPrincipal


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


class _Request:
    def __init__(self, body: dict) -> None:
        self._body = body
        self.disconnected = False

    async def json(self):
        return dict(self._body)

    async def is_disconnected(self) -> bool:
        return self.disconnected


class _BlockingUseCase:
    def __init__(self, run: AgentRun, store: InMemoryExecutionStateStore) -> None:
        self.run = run
        self.store = store
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.release = asyncio.Event()
        self.completed = asyncio.Event()

    async def execute(self, input_dto):
        del input_dto
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
        await channel.emit(
            "token",
            content="partial over http",
            visibility="assistant",
            channel="final",
            phase="response_generation",
        )
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        self.completed.set()
        return SimpleNamespace(
            model_dump=lambda **_: {
                "run_id": str(self.run.id),
                "session_id": str(self.run.session_id),
                "trace_id": str(self.run.trace_id),
                "answer": "completed after disconnect",
            }
        )


def _run() -> AgentRun:
    return AgentRun(
        session_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="draft",
        origin="runtime_api",
        input_message="stream this",
        execution_snapshot={},
    )


def _body(run: AgentRun) -> dict:
    return {
        "project_id": str(run.project_id),
        "agent_id": str(run.agent_id),
        "message": run.input_message,
        "execution_context": "playground",
    }


def _runtime_principal(run: AgentRun) -> ProjectApiPrincipal:
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=run.project_id,
        key_prefix="rai_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        agent_id=run.agent_id,
        target_type="agent",
        target_id=run.agent_id,
        environment=run.environment,
        interfaces=frozenset({"http", "stream"}),
        authenticated_at=datetime.now(UTC),
    )


async def _allow_environment(*_args) -> None:
    return None


async def _next_body_frame(iterator, event_type: str) -> str:
    while True:
        chunk = await asyncio.wait_for(anext(iterator), timeout=2)
        text = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
        if f"event: {event_type}" in text:
            return text


@pytest.mark.asyncio
async def test_http_stream_stays_attached_until_durable_cancelled_terminal() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _BlockingUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)
    control = AgentRunReattachService(transactions=transactions, state_store=store)
    request = _Request(_body(run))

    response = await handle_ask_stream(request, service, _allow_environment)
    iterator = response.body_iterator

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"

    meta = await _next_body_frame(iterator, "meta")
    assert str(run.id) in meta
    assert str(run.session_id) in meta
    await asyncio.wait_for(use_case.started.wait(), timeout=1)

    # Client B issues the same control operation used by POST /runtime/runs/{id}/cancel
    # while client A keeps observing the original StreamingResponse.
    result = await control.cancel(run_id=run.id, principal=_runtime_principal(run))
    assert result == {"run_id": str(run.id), "status": "cancel_requested"}

    terminal = await _next_body_frame(iterator, "cancelled")
    assert '"persisted": true' in terminal
    assert '"output": "partial over http"' in terminal
    assert str(run.session_id) in terminal
    await asyncio.wait_for(use_case.cancelled.wait(), timeout=1)
    assert transactions.repositories.runs.run.status == AgentRunStatus.CANCELLED


@pytest.mark.asyncio
async def test_http_disconnect_disposes_only_observer_and_does_not_cancel_run() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    transactions = _Transactions(run)
    use_case = _BlockingUseCase(run, store)
    service = AskAgentStreamService(use_case, transactions, state_store=store)
    request = _Request(_body(run))

    response = await handle_ask_stream(request, service, _allow_environment)
    iterator = response.body_iterator

    await _next_body_frame(iterator, "meta")
    await asyncio.wait_for(use_case.started.wait(), timeout=1)
    request.disconnected = True

    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(iterator), timeout=1)

    assert use_case.cancelled.is_set() is False
    assert transactions.repositories.runs.run.status == AgentRunStatus.RUNNING

    use_case.release.set()
    await asyncio.wait_for(use_case.completed.wait(), timeout=1)
    assert use_case.cancelled.is_set() is False
