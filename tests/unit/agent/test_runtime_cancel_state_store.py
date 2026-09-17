from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.agent_run_reattach_service import AgentRunReattachService
from shared.infra.errors import ConflictError
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.security.principal import ProjectApiPrincipal


class _Runs:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(runs=_Runs(run), project_access=SimpleNamespace())

    async def read(self, operation):
        return await operation(self.repositories, None)


class _UnavailableStore:
    async def get(self, _run_id):
        raise RuntimeError("redis unavailable")


class _MustNotTouchStore:
    async def get(self, _run_id):
        raise AssertionError("terminal cancel retry must not require hot state")

    async def request_cancel(self, _run_id):
        raise AssertionError("terminal cancel retry must not enqueue another request")


def _run() -> AgentRun:
    return AgentRun(
        session_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="production",
        origin="runtime_api",
        input_message="hello",
        execution_snapshot={},
    )


def _principal(run: AgentRun) -> ProjectApiPrincipal:
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=run.project_id,
        key_prefix="rai_live_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        target_type="agent",
        target_id=run.agent_id,
        agent_id=run.agent_id,
        environment=run.environment,
        interfaces=frozenset({"http", "stream"}),
        authenticated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_direct_agent_cancel_rejects_missing_hot_state_for_non_terminal_run() -> None:
    run = _run()
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=InMemoryExecutionStateStore(),
    )

    with pytest.raises(ConflictError, match="no active runtime state"):
        await service.cancel(run_id=run.id, principal=_principal(run))


@pytest.mark.asyncio
async def test_terminal_cancel_retry_is_idempotent_without_touching_hot_state() -> None:
    run = _run()
    run.status = AgentRunStatus.CANCELLED
    run.result = {
        "answer": "partial",
        "partial": True,
        "cancelled": True,
    }
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=_MustNotTouchStore(),
    )
    principal = _principal(run)

    first = await service.cancel(run_id=run.id, principal=principal)
    repeated = await service.cancel(run_id=run.id, principal=principal)

    expected = {"run_id": str(run.id), "status": "cancelled"}
    assert first == expected
    assert repeated == expected


@pytest.mark.asyncio
async def test_agent_reattach_degrades_to_durable_terminal_when_hot_store_is_unavailable() -> None:
    run = _run()
    run.status = AgentRunStatus.CANCELLED
    run.result = {
        "answer": "durable partial",
        "partial": True,
        "cancelled": True,
    }
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=_UnavailableStore(),
    )

    stream = service.stream_sse(run_id=run.id, principal=_principal(run))
    frame = await anext(stream)

    assert "event: run.state" in frame
    assert f'\"run_id\": \"{run.id}\"' in frame
    assert f'\"session_id\": \"{run.session_id}\"' in frame
    assert '\"status\": \"cancelled\"' in frame
    assert '\"output\": \"durable partial\"' in frame
    assert '\"realtime_available\": false' in frame

    with pytest.raises(StopAsyncIteration):
        await anext(stream)
