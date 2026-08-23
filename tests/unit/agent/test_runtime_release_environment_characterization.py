from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.runtime.release_runtime_resolver import (
    ReleaseRuntimeResolver,
)
from modules.agent.domain.entities import Agent, AgentRelease, ProviderCredential, ProviderModel
from modules.agent.domain.enums import (
    AgentStatus,
    CredentialStatus,
    Provider,
    ProviderModelStatus,
    ReleaseStatus,
)
from modules.agent.domain.errors import AgentNotFoundError, RuntimeEnvironmentNotReadyError
from shared.infra.errors import ValidationError


class MemoryReleaseRepository:
    def __init__(self, *releases):
        self.releases = {release.id: release for release in releases}

    async def get_by_id(self, release_id):
        return self.releases.get(release_id)

    async def get_active_production(self, agent_id):
        return next(
            (
                release
                for release in self.releases.values()
                if release.agent_id == agent_id
                and release.status == ReleaseStatus.production
            ),
            None,
        )

    async def list_by_status(self, agent_id, status):
        value = status.value if hasattr(status, "value") else status
        return [
            release
            for release in self.releases.values()
            if release.agent_id == agent_id
            and getattr(release.status, "value", release.status) == value
        ]


def _release(*, project_id, agent_id, version, status, model, runtime_config=None):
    return AgentRelease(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        version=version,
        status=status,
        provider="openai",
        model=model,
        runtime_config=runtime_config,
    )


def _agent(*, project_id, agent_id=None, model="draft-model", status=AgentStatus.active):
    return Agent(
        id=agent_id or uuid4(),
        project_id=project_id,
        name="agent",
        provider=Provider.openai,
        model=model,
        status=status,
    )


def _uow(agent, releases=None, provider_models=None, provider_credentials=None):
    return SimpleNamespace(
        agents=SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        releases=releases,
        sessions=None,
        provider_models=provider_models,
        provider_credentials=provider_credentials,
    )


async def _load(resolver, uow, input_dto):
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        result = await resolver._load_agent(uow, input_dto)
        return result, context
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_production_runtime_binds_active_production_release():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    production = _release(
        project_id=project_id,
        agent_id=agent.id,
        version="2.0.0",
        status=ReleaseStatus.production,
        model="production-model",
        runtime_config={"tools": {"tool_ids": []}},
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="production",
    )

    loaded, context = await _load(
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
        _uow(agent, MemoryReleaseRepository(production)),
        input_dto,
    )

    assert loaded.model == "production-model"
    assert input_dto.loaded_release_id == production.id
    assert context.agent_release_id == production.id
    assert context.agent_release_version == "2.0.0"
    assert loaded.settings["runtime_config"] == production.runtime_config


@pytest.mark.asyncio
async def test_production_runtime_fails_when_no_production_release_exists():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="production",
    )

    with pytest.raises(RuntimeEnvironmentNotReadyError):
        await _load(
            ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
            _uow(agent, MemoryReleaseRepository()),
            input_dto,
        )


@pytest.mark.asyncio
async def test_production_runtime_requires_release_repository():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="production",
    )

    with pytest.raises(ValidationError, match="requires release repository"):
        await _load(
            ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
            _uow(agent, None),
            input_dto,
        )


@pytest.mark.asyncio
async def test_staging_runtime_uses_newest_staging_release():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    older = _release(
        project_id=project_id,
        agent_id=agent.id,
        version="staging-1",
        status=ReleaseStatus.staging,
        model="old-model",
    )
    newer = _release(
        project_id=project_id,
        agent_id=agent.id,
        version="staging-2",
        status=ReleaseStatus.staging,
        model="new-model",
    )
    older.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
    newer.created_at = datetime.now(timezone.utc)
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="staging",
    )

    loaded, context = await _load(
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
        _uow(agent, MemoryReleaseRepository(older, newer)),
        input_dto,
    )

    assert loaded.model == "new-model"
    assert input_dto.loaded_release_id == newer.id
    assert context.agent_release_id == newer.id


@pytest.mark.asyncio
async def test_staging_runtime_fails_when_no_staging_release_exists():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="staging",
    )

    with pytest.raises(RuntimeEnvironmentNotReadyError):
        await _load(
            ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
            _uow(agent, MemoryReleaseRepository()),
            input_dto,
        )


@pytest.mark.asyncio
async def test_explicit_pinned_release_wins_over_current_production():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    pinned = _release(
        project_id=project_id,
        agent_id=agent.id,
        version="1.0.0",
        status=ReleaseStatus.released,
        model="pinned-model",
    )
    production = _release(
        project_id=project_id,
        agent_id=agent.id,
        version="2.0.0",
        status=ReleaseStatus.production,
        model="current-model",
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="network run",
        execution_context="production",
        loaded_release_id=pinned.id,
        metadata={"source": "network_runtime"},
    )

    loaded, context = await _load(
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
        _uow(agent, MemoryReleaseRepository(pinned, production)),
        input_dto,
    )

    assert loaded.model == "pinned-model"
    assert input_dto.loaded_release_id == pinned.id
    assert context.agent_release_id == pinned.id


@pytest.mark.asyncio
async def test_invalid_pinned_release_is_rejected():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    other_agent_release = _release(
        project_id=project_id,
        agent_id=uuid4(),
        version="1.0.0",
        status=ReleaseStatus.released,
        model="other",
    )
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        loaded_release_id=other_agent_release.id,
    )

    with pytest.raises(ValidationError, match="Pinned Agent release was not found"):
        await _load(
            ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
            _uow(agent, MemoryReleaseRepository(other_agent_release)),
            input_dto,
        )


@pytest.mark.asyncio
async def test_playground_uses_latest_draft_release_when_available():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    old = _release(
        project_id=project_id,
        agent_id=agent.id,
        version="draft-1",
        status=ReleaseStatus.draft,
        model="old-draft-model",
    )
    new = _release(
        project_id=project_id,
        agent_id=agent.id,
        version="draft-2",
        status=ReleaseStatus.draft,
        model="new-draft-model",
        runtime_config={"tools": {"tool_ids": []}},
    )
    old.created_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    new.created_at = datetime.now(timezone.utc)
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="playground",
    )

    loaded, context = await _load(
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
        _uow(agent, MemoryReleaseRepository(old, new)),
        input_dto,
    )

    assert loaded.model == "new-draft-model"
    assert context.agent_release_id == new.id
    assert loaded.settings["runtime_config"] == new.runtime_config


@pytest.mark.asyncio
async def test_playground_without_release_uses_live_agent_configuration():
    project_id = uuid4()
    agent = _agent(project_id=project_id, model="live-draft-model")
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="playground",
    )

    loaded, context = await _load(
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
        _uow(agent, MemoryReleaseRepository()),
        input_dto,
    )

    assert loaded.model == "live-draft-model"
    assert context.agent_release_id is None


@pytest.mark.asyncio
async def test_unsupported_execution_context_is_rejected():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
        execution_context="invalid-environment",
    )

    with pytest.raises(ValueError, match="Unsupported execution context"):
        await _load(
            ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
            _uow(agent, MemoryReleaseRepository()),
            input_dto,
        )


@pytest.mark.asyncio
async def test_agent_must_exist_in_requested_project():
    project_id = uuid4()
    agent = _agent(project_id=uuid4())
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
    )

    with pytest.raises(AgentNotFoundError):
        await _load(
            ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
            _uow(agent, MemoryReleaseRepository()),
            input_dto,
        )


@pytest.mark.asyncio
async def test_inactive_agent_cannot_execute():
    project_id = uuid4()
    agent = _agent(project_id=project_id, status=AgentStatus.inactive)
    input_dto = AskInput(
        project_id=project_id,
        agent_id=agent.id,
        message="hello",
    )

    with pytest.raises(ValidationError, match="Agent is not active"):
        await _load(
            ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver),
            _uow(agent, MemoryReleaseRepository()),
            input_dto,
        )


def test_runtime_model_is_required():
    project_id = uuid4()
    agent = _agent(project_id=project_id, model="")

    with pytest.raises(ValidationError, match="Agent model is not configured"):
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._validate_runtime_model(agent)


def test_expired_provider_credential_is_rejected():
    credential = ProviderCredential(
        project_id=uuid4(),
        provider=Provider.openai,
        name="expired",
        encrypted_secret="secret",
        status=CredentialStatus.active,
        metadata={
            "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        },
    )

    with pytest.raises(ValidationError, match="expired"):
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._validate_credential_runtime_status(
            credential
        )


def test_invalid_provider_credential_expiration_is_rejected():
    credential = ProviderCredential(
        project_id=uuid4(),
        provider=Provider.openai,
        name="invalid-expiration",
        encrypted_secret="secret",
        status=CredentialStatus.active,
        metadata={"expires_at": "not-a-date"},
    )

    with pytest.raises(ValidationError, match="expiration date is invalid"):
        ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._validate_credential_runtime_status(
            credential
        )


@pytest.mark.asyncio
async def test_provider_model_binding_resolves_model_credential_and_pricing_snapshot():
    project_id = uuid4()
    credential = ProviderCredential(
        id=uuid4(),
        project_id=project_id,
        provider=Provider.openai,
        name="primary",
        encrypted_secret="secret",
        status=CredentialStatus.active,
    )
    provider_model = ProviderModel(
        id=uuid4(),
        project_id=project_id,
        provider_credential_id=credential.id,
        name="primary-model",
        model="gpt-test",
        status=ProviderModelStatus.active,
        metadata={"input_cost_per_million": 1.0, "output_cost_per_million": 2.0},
    )
    agent = _agent(project_id=project_id)
    agent.provider_model_id = provider_model.id
    provider_models = SimpleNamespace(get_by_id=AsyncMock(return_value=provider_model))
    credentials = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))
    uow = _uow(
        agent,
        MemoryReleaseRepository(),
        provider_models=provider_models,
        provider_credentials=credentials,
    )

    resolved = await ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._resolve_provider_model_refs(
        uow, agent
    )

    assert resolved.model == "gpt-test"
    assert resolved.provider_credential_id == credential.id
    assert resolved.provider == Provider.openai
    assert resolved.settings["model_pricing"]["provider_model_id"] == str(provider_model.id)