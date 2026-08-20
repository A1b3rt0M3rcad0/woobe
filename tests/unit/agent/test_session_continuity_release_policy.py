from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.runtime.session_continuity_runtime_resolver import (
    SessionContinuityReleaseRuntimeResolver,
)
from modules.agent.domain.entities import Agent, AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from shared.infra.errors import ConflictError


class MemoryReleaseRepository:
    def __init__(self, *items):
        self.items = {item.id: item for item in items}

    async def get_by_id(self, release_id):
        return self.items.get(release_id)

    async def get_active_production(self, agent_id):
        return next(
            (
                item
                for item in self.items.values()
                if item.agent_id == agent_id and item.status == ReleaseStatus.production
            ),
            None,
        )

    async def list_by_status(self, agent_id, status):
        value = status.value if hasattr(status, "value") else status
        return [
            item
            for item in self.items.values()
            if item.agent_id == agent_id
            and getattr(item.status, "value", item.status) == value
        ]


def _release(*, project_id, agent_id, version, status, model):
    return AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version=version,
        status=status,
        provider="openai",
        model=model,
        session_mode="stateless",
    )


@pytest.mark.asyncio
async def test_existing_production_session_follows_current_production_release() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    opened = _release(
        project_id=project_id,
        agent_id=agent_id,
        version="v1",
        status=ReleaseStatus.released,
        model="model-v1",
    )
    current = _release(
        project_id=project_id,
        agent_id=agent_id,
        version="v2",
        status=ReleaseStatus.production,
        model="model-v2",
    )
    agent = Agent(
        id=agent_id,
        project_id=project_id,
        model="draft-model",
        session_mode="stateful",
    )
    session = SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="production",
        opened_release_id=opened.id,
        data=None,
    )
    uow = SimpleNamespace(
        agents=SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        releases=MemoryReleaseRepository(opened, current),
        sessions=SimpleNamespace(get_by_id=AsyncMock(return_value=session)),
        provider_models=None,
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=uuid4(),
        message="continue",
        execution_context="production",
        loaded_release_id=opened.id,
    )

    loaded = await SessionContinuityReleaseRuntimeResolver.__new__(
        SessionContinuityReleaseRuntimeResolver
    )._load_agent(uow, input_dto)

    assert loaded.model == "model-v2"
    assert input_dto.loaded_release_id == current.id
    assert getattr(loaded.session_mode, "value", loaded.session_mode) == "stateful"
    assert session.opened_release_id == opened.id


@pytest.mark.asyncio
async def test_session_environment_remains_an_invariant() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    session = SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="staging",
        opened_release_id=uuid4(),
        data=None,
    )
    uow = SimpleNamespace(
        sessions=SimpleNamespace(get_by_id=AsyncMock(return_value=session)),
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        session_id=uuid4(),
        message="continue",
        execution_context="production",
    )

    with pytest.raises(ConflictError, match="belongs to staging"):
        await SessionContinuityReleaseRuntimeResolver.__new__(
            SessionContinuityReleaseRuntimeResolver
        )._session_runtime_binding(uow, input_dto)


@pytest.mark.asyncio
async def test_network_runtime_keeps_explicit_agent_release_binding() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    network_release = _release(
        project_id=project_id,
        agent_id=agent_id,
        version="v1",
        status=ReleaseStatus.released,
        model="network-bound-model",
    )
    production = _release(
        project_id=project_id,
        agent_id=agent_id,
        version="v2",
        status=ReleaseStatus.production,
        model="standalone-production-model",
    )
    agent = Agent(id=agent_id, project_id=project_id, model="draft-model")
    uow = SimpleNamespace(
        agents=SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        releases=MemoryReleaseRepository(network_release, production),
        sessions=SimpleNamespace(),
        provider_models=None,
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        message="network invocation",
        execution_context="production",
        loaded_release_id=network_release.id,
        metadata={"source": "network_runtime"},
    )

    loaded = await SessionContinuityReleaseRuntimeResolver.__new__(
        SessionContinuityReleaseRuntimeResolver
    )._load_agent(uow, input_dto)

    assert loaded.model == "network-bound-model"
    assert input_dto.loaded_release_id == network_release.id


@pytest.mark.asyncio
async def test_new_production_session_records_run_release_as_opening_provenance() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    agent = Agent(id=agent_id, project_id=project_id, model="model", session_mode="stateful")
    created = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="draft",
        opened_release_id=None,
        data=None,
    )
    session_repo = SimpleNamespace(
        create=AsyncMock(return_value=created),
        update=AsyncMock(),
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent_id,
        message="hello",
        execution_context="production",
        loaded_release_id=release_id,
        metadata={"source": "playground"},
    )
    context = new_execution_context()
    context.agent_release_id = release_id
    context.agent_release_version = "v3"
    token = current_execution.set(context)
    try:
        session = await SessionContinuityReleaseRuntimeResolver.__new__(
            SessionContinuityReleaseRuntimeResolver
        )._resolve_session(session_repo, input_dto, agent)
    finally:
        current_execution.reset(token)

    assert session.runtime_environment == "production"
    assert session.opened_release_id == release_id
    assert session.data == {"source": "playground"}
    session_repo.update.assert_awaited_once()
