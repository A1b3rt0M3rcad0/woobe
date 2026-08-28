from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.run import AgentRun
from modules.agent.infra.execution.agent_run_reattach_service import AgentRunReattachService
from shared.contracts.errors import AuthorizationError, NotFoundError
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore
from shared.security.principal import ProjectApiPrincipal


class _Runs:
    def __init__(self, run: AgentRun) -> None:
        self.run = run

    async def get_by_id(self, run_id):
        return self.run if self.run.id == run_id else None


class _Transactions:
    def __init__(self, run: AgentRun) -> None:
        self.repositories = SimpleNamespace(runs=_Runs(run))

    async def read(self, operation):
        return await operation(self.repositories, None)


def _run() -> AgentRun:
    return AgentRun(
        project_id=uuid4(),
        agent_id=uuid4(),
        trace_id=uuid4(),
        environment="production",
        origin="runtime_api",
        input_message="authorize this run",
        execution_snapshot={},
    )


def _principal(
    run: AgentRun,
    *,
    project_id=None,
    target_id=None,
    environment: str | None = None,
) -> ProjectApiPrincipal:
    return ProjectApiPrincipal(
        api_key_id=uuid4(),
        project_id=project_id or run.project_id,
        key_prefix="rai_live_test",
        scopes=frozenset({"runtime:execute"}),
        kind="runtime",
        agent_id=target_id or run.agent_id,
        target_type="agent",
        target_id=target_id or run.agent_id,
        environment=environment if environment is not None else run.environment,
        interfaces=frozenset({"http", "stream"}),
        authenticated_at=datetime.now(UTC),
    )


def _service(run: AgentRun) -> AgentRunReattachService:
    return AgentRunReattachService(
        transactions=_Transactions(run),
        state_store=InMemoryExecutionStateStore(),
    )


@pytest.mark.asyncio
async def test_runtime_key_must_match_concrete_run_project() -> None:
    run = _run()

    with pytest.raises(AuthorizationError, match="Project"):
        await _service(run).authorize(
            run_id=run.id,
            principal=_principal(run, project_id=uuid4()),
        )


@pytest.mark.asyncio
async def test_runtime_key_must_match_concrete_run_agent_target() -> None:
    run = _run()

    with pytest.raises(NotFoundError, match="Agent Run"):
        await _service(run).authorize(
            run_id=run.id,
            principal=_principal(run, target_id=uuid4()),
        )


@pytest.mark.asyncio
async def test_runtime_key_must_match_concrete_run_environment() -> None:
    run = _run()

    with pytest.raises(NotFoundError, match="Agent Run"):
        await _service(run).authorize(
            run_id=run.id,
            principal=_principal(run, environment="staging"),
        )


@pytest.mark.asyncio
async def test_matching_runtime_key_can_control_concrete_run() -> None:
    run = _run()

    await _service(run).authorize(
        run_id=run.id,
        principal=_principal(run),
    )
