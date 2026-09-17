from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.run import AgentRun, AgentRunStatus
from modules.agent.infra.execution.agent_run_reattach_service import AgentRunReattachService
from shared.infra.errors import AuthorizationError, NotFoundError
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.security.principal import ProjectApiPrincipal


class _Runs:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(
            runs=_Runs(run),
            project_access=SimpleNamespace(),
        )

    async def read(self, operation):
        return await operation(self.repositories, None)


def _run() -> AgentRun:
    return AgentRun(
        session_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="production",
        origin="runtime_api",
        input_message="cancel me",
        execution_snapshot={},
    )


def _principal(run: AgentRun, **overrides) -> ProjectApiPrincipal:
    values = {
        "api_key_id": uuid4(),
        "project_id": run.project_id,
        "key_prefix": "rai_live_test",
        "scopes": frozenset({"runtime:execute"}),
        "kind": "runtime",
        "target_type": "agent",
        "target_id": run.agent_id,
        "agent_id": run.agent_id,
        "environment": run.environment,
        "interfaces": frozenset({"http", "stream"}),
        "authenticated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ProjectApiPrincipal(**values)


@pytest.mark.asyncio
async def test_agent_runtime_cancel_authorizes_exact_runtime_target_and_environment() -> None:
    run = _run()
    store = InMemoryExecutionStateStore()
    await store.create(
        run.id,
        {"status": "running", "session_id": str(run.session_id)},
        ttl_seconds=3600,
    )
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=store,
    )

    response = await service.cancel(run_id=run.id, principal=_principal(run))

    assert response == {"run_id": str(run.id), "status": "cancel_requested"}
    assert await store.is_cancel_requested(run.id) is True


@pytest.mark.asyncio
async def test_agent_runtime_cancel_rejects_runtime_key_from_another_project() -> None:
    run = _run()
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=InMemoryExecutionStateStore(),
    )

    with pytest.raises(AuthorizationError):
        await service.cancel(
            run_id=run.id,
            principal=_principal(run, project_id=uuid4()),
        )


@pytest.mark.asyncio
async def test_agent_runtime_cancel_hides_run_from_wrong_runtime_target() -> None:
    run = _run()
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=InMemoryExecutionStateStore(),
    )

    with pytest.raises(NotFoundError):
        await service.cancel(
            run_id=run.id,
            principal=_principal(run, target_id=uuid4(), agent_id=uuid4()),
        )


@pytest.mark.asyncio
async def test_agent_runtime_cancel_hides_run_from_wrong_environment() -> None:
    run = _run()
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=InMemoryExecutionStateStore(),
    )

    with pytest.raises(NotFoundError):
        await service.cancel(
            run_id=run.id,
            principal=_principal(run, environment="staging"),
        )


@pytest.mark.asyncio
async def test_agent_runtime_cancel_is_terminal_state_safe_without_hot_state() -> None:
    run = _run()
    run.status = AgentRunStatus.COMPLETED
    service = AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=InMemoryExecutionStateStore(),
    )

    response = await service.cancel(run_id=run.id, principal=_principal(run))

    assert response == {"run_id": str(run.id), "status": "completed"}
