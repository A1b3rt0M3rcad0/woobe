from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import (
    CreateAgentInput,
    GetAgentInput,
    ListAgentsInput,
    UpdateAgentInput,
)
from modules.agent.application.use_cases import (
    CreateAgentUseCase,
    GetAgentByIdUseCase,
    ListAgentsUseCase,
    UpdateAgentUseCase,
)
from modules.agent.domain.entities import Agent, ProviderCredential, ProviderModel
from modules.agent.domain.enums import (
    AgentStatus,
    CredentialStatus,
    Provider,
    ProviderModelStatus,
)
from modules.agent.domain.errors import (
    AgentNotFoundError,
    CredentialNotFoundError,
    ModelConfigNotFoundError,
)
from shared.infra.errors import ConflictError, ValidationError


def _credential(*, project_id, credential_id=None, status=CredentialStatus.active):
    return ProviderCredential(
        id=credential_id or uuid4(),
        project_id=project_id,
        provider=Provider.openai,
        name="primary",
        encrypted_secret="encrypted",
        status=status,
    )


def _provider_model(
    *,
    project_id,
    credential_id,
    model_id=None,
    model="gpt-test",
    status=ProviderModelStatus.active,
    metadata=None,
):
    return ProviderModel(
        id=model_id or uuid4(),
        project_id=project_id,
        provider_credential_id=credential_id,
        name=model,
        model=model,
        status=status,
        metadata=metadata or {},
    )


def _agent(*, project_id, agent_id=None, status=AgentStatus.active):
    return Agent(
        id=agent_id or uuid4(),
        project_id=project_id,
        name="Support Agent",
        description="Answers customer questions",
        system_prompt="Be precise",
        provider=Provider.openai,
        model="gpt-test",
        status=status,
    )


def _passthrough(mock):
    async def _call(value):
        return value

    mock.side_effect = _call


def _deps(*, existing_agent=None, credential=None, provider_model=None):
    agent_repo = SimpleNamespace(
        save=AsyncMock(),
        update=AsyncMock(),
        get_by_id=AsyncMock(return_value=existing_agent),
        list_by_project=AsyncMock(return_value=[]),
    )
    _passthrough(agent_repo.save)
    _passthrough(agent_repo.update)
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))
    provider_model_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=provider_model),
        list_by_credential=AsyncMock(return_value=[]),
    )
    outbox = SimpleNamespace(write=AsyncMock())
    return agent_repo, credential_repo, provider_model_repo, outbox


@pytest.mark.asyncio
async def test_create_agent_persists_forces_strict_json_and_emits_created_event():
    project_id = uuid4()
    agent_repo, credential_repo, _, outbox = _deps()
    use_case = CreateAgentUseCase(agent_repo, credential_repo, outbox)

    saved = await use_case.execute(
        CreateAgentInput(
            project_id=project_id,
            name="Support Agent",
            model="gpt-test",
            settings={
                "response_format": {
                    "enabled": True,
                    "type": "json",
                    "strict": False,
                    "schema": {"type": "object"},
                }
            },
        )
    )

    assert saved.project_id == project_id
    assert saved.settings["response_format"]["strict"] is True
    agent_repo.save.assert_awaited_once()
    outbox.write.assert_awaited_once()
    event = outbox.write.await_args.args[0]
    assert event.payload["agent_id"] == str(saved.id)
    assert event.payload["project_id"] == str(project_id)
    assert event.event_type == "agent.agent.created.v1"


@pytest.mark.asyncio
async def test_create_agent_does_not_force_strict_when_json_response_is_disabled():
    project_id = uuid4()
    agent_repo, credential_repo, _, outbox = _deps()

    saved = await CreateAgentUseCase(agent_repo, credential_repo, outbox).execute(
        CreateAgentInput(
            project_id=project_id,
            name="Text Agent",
            model="gpt-test",
            settings={
                "response_format": {
                    "enabled": False,
                    "type": "json",
                    "strict": False,
                }
            },
        )
    )

    assert saved.settings["response_format"]["strict"] is False


@pytest.mark.asyncio
async def test_create_agent_resolves_explicit_provider_model_and_credential():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    provider_model = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        model="gpt-resolved",
    )
    agent_repo, credential_repo, provider_models, outbox = _deps(
        credential=credential,
        provider_model=provider_model,
    )

    saved = await CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_models,
    ).execute(
        CreateAgentInput(
            project_id=project_id,
            provider_model_id=provider_model.id,
            name="Resolved Agent",
            model="client-value-is-not-authoritative",
        )
    )

    assert saved.provider_model_id == provider_model.id
    assert saved.provider_credential_id == credential.id
    assert saved.provider == Provider.openai
    assert saved.model == "gpt-resolved"


@pytest.mark.asyncio
async def test_create_agent_resolves_implicit_provider_model_deterministically():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    first = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        model_id=UUID(int=1),
        model="shared-model",
    )
    second = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        model_id=UUID(int=2),
        model="shared-model",
    )
    agent_repo, credential_repo, provider_models, outbox = _deps(
        credential=credential,
        provider_model=first,
    )
    provider_models.list_by_credential.return_value = [second, first]

    saved = await CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_models,
    ).execute(
        CreateAgentInput(
            project_id=project_id,
            provider_credential_id=credential.id,
            name="Implicit Binding",
            model="shared-model",
        )
    )

    assert saved.provider_model_id == first.id
    provider_models.list_by_credential.assert_awaited_once_with(credential.id)


@pytest.mark.asyncio
async def test_implicit_binding_ignores_embedding_models_and_keeps_direct_credential():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    embedding = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        model="text-embedding-3-small",
        metadata={"capability": "embedding"},
    )
    agent_repo, credential_repo, provider_models, outbox = _deps(credential=credential)
    provider_models.list_by_credential.return_value = [embedding]

    saved = await CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_models,
    ).execute(
        CreateAgentInput(
            project_id=project_id,
            provider_credential_id=credential.id,
            name="Chat Agent",
            model="text-embedding-3-small",
        )
    )

    assert saved.provider_model_id is None
    assert saved.provider_credential_id == credential.id


@pytest.mark.asyncio
async def test_explicit_embedding_provider_model_is_rejected():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    embedding = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        metadata={"type": "embeddings"},
    )
    agent_repo, credential_repo, provider_models, outbox = _deps(
        credential=credential,
        provider_model=embedding,
    )

    with pytest.raises(ConflictError, match="not compatible with agent runtime"):
        await CreateAgentUseCase(
            agent_repo,
            credential_repo,
            outbox,
            provider_models,
        ).execute(
            CreateAgentInput(
                project_id=project_id,
                provider_model_id=embedding.id,
                name="Invalid Agent",
                model="ignored",
            )
        )

    agent_repo.save.assert_not_awaited()
    outbox.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_provider_model_is_rejected():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    model = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        status=ProviderModelStatus.inactive,
    )
    agent_repo, credential_repo, provider_models, outbox = _deps(
        credential=credential,
        provider_model=model,
    )

    with pytest.raises(ValidationError, match="Provider model must be active"):
        await CreateAgentUseCase(
            agent_repo,
            credential_repo,
            outbox,
            provider_models,
        ).execute(
            CreateAgentInput(
                project_id=project_id,
                provider_model_id=model.id,
                name="Inactive Model",
                model="ignored",
            )
        )


@pytest.mark.asyncio
async def test_missing_provider_model_and_missing_direct_credential_are_rejected():
    project_id = uuid4()
    agent_repo, credential_repo, provider_models, outbox = _deps()
    provider_models.get_by_id.return_value = None

    with pytest.raises(ModelConfigNotFoundError):
        await CreateAgentUseCase(
            agent_repo,
            credential_repo,
            outbox,
            provider_models,
        ).execute(
            CreateAgentInput(
                project_id=project_id,
                provider_model_id=uuid4(),
                name="Missing Model",
                model="ignored",
            )
        )

    with pytest.raises(CredentialNotFoundError):
        await CreateAgentUseCase(agent_repo, credential_repo, outbox).execute(
            CreateAgentInput(
                project_id=project_id,
                provider_credential_id=uuid4(),
                name="Missing Credential",
                model="gpt-test",
            )
        )


@pytest.mark.asyncio
async def test_inactive_provider_credential_is_rejected_for_model_binding():
    project_id = uuid4()
    credential = _credential(project_id=project_id, status=CredentialStatus.revoked)
    model = _provider_model(project_id=project_id, credential_id=credential.id)
    agent_repo, credential_repo, provider_models, outbox = _deps(
        credential=credential,
        provider_model=model,
    )

    with pytest.raises(ValidationError, match="Provider credential must be active"):
        await CreateAgentUseCase(
            agent_repo,
            credential_repo,
            outbox,
            provider_models,
        ).execute(
            CreateAgentInput(
                project_id=project_id,
                provider_model_id=model.id,
                name="Revoked Credential",
                model="ignored",
            )
        )


@pytest.mark.asyncio
async def test_fallback_provider_model_binding_is_resolved_independently():
    project_id = uuid4()
    fallback_credential = _credential(project_id=project_id)
    fallback_model = _provider_model(
        project_id=project_id,
        credential_id=fallback_credential.id,
        model="fallback-model",
    )
    agent_repo, credential_repo, provider_models, outbox = _deps(
        credential=fallback_credential,
        provider_model=fallback_model,
    )

    saved = await CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_models,
    ).execute(
        CreateAgentInput(
            project_id=project_id,
            fallback_provider_model_id=fallback_model.id,
            name="Fallback Agent",
            model="primary-model",
        )
    )

    assert saved.fallback_provider_model_id == fallback_model.id
    assert saved.fallback_credential_id == fallback_credential.id
    assert saved.fallback_provider == Provider.openai
    assert saved.fallback_model == "fallback-model"


@pytest.mark.asyncio
async def test_update_agent_not_found_does_not_write_or_emit_event():
    agent_repo, credential_repo, _, outbox = _deps(existing_agent=None)

    with pytest.raises(AgentNotFoundError):
        await UpdateAgentUseCase(agent_repo, credential_repo, outbox).execute(
            uuid4(),
            UpdateAgentInput(name="new name"),
        )

    agent_repo.update.assert_not_awaited()
    outbox.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_blocks_deactivation_while_network_drafts_reference_agent():
    project_id = uuid4()
    existing = _agent(project_id=project_id)
    agent_repo, credential_repo, _, outbox = _deps(existing_agent=existing)
    reader = SimpleNamespace(
        list_draft_references=AsyncMock(
            return_value=[
                {"name": f"Network {index}", "id": str(uuid4())}
                for index in range(7)
            ]
        )
    )
    use_case = UpdateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        network_usage_reader=reader,
    )

    with pytest.raises(ConflictError, match="and 2 more"):
        await use_case.execute(
            existing.id,
            UpdateAgentInput(status=AgentStatus.inactive),
        )

    reader.list_draft_references.assert_awaited_once_with(
        project_id=project_id,
        agent_id=existing.id,
    )
    agent_repo.update.assert_not_awaited()
    outbox.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_allows_unreferenced_deactivation_and_emits_updated_event():
    project_id = uuid4()
    existing = _agent(project_id=project_id)
    agent_repo, credential_repo, _, outbox = _deps(existing_agent=existing)
    reader = SimpleNamespace(list_draft_references=AsyncMock(return_value=[]))

    result = await UpdateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        network_usage_reader=reader,
    ).execute(
        existing.id,
        UpdateAgentInput(
            name="Updated Agent",
            status=AgentStatus.inactive,
            settings={
                "response_format": {
                    "enabled": True,
                    "type": "json",
                    "strict": False,
                }
            },
        ),
    )

    assert result.status == AgentStatus.inactive
    assert result.name == "Updated Agent"
    assert result.settings["response_format"]["strict"] is True
    agent_repo.update.assert_awaited_once()
    outbox.write.assert_awaited_once()
    event = outbox.write.await_args.args[0]
    assert event.payload["agent_id"] == str(existing.id)
    assert event.event_type == "agent.agent.updated.v1"


@pytest.mark.asyncio
async def test_list_agents_handles_missing_project_and_maps_entities():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    agent_repo, _, _, _ = _deps()

    empty = await ListAgentsUseCase(agent_repo).execute(ListAgentsInput(project_id=None))
    assert empty == []
    agent_repo.list_by_project.assert_not_awaited()

    agent_repo.list_by_project.return_value = [agent]
    result = await ListAgentsUseCase(agent_repo).execute(
        ListAgentsInput(project_id=project_id)
    )

    agent_repo.list_by_project.assert_awaited_once_with(project_id)
    assert len(result) == 1
    assert result[0].id == agent.id
    assert result[0].name == agent.name
    assert result[0].status == agent.status


@pytest.mark.asyncio
async def test_get_agent_success_and_not_found_contracts():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    agent_repo, _, _, _ = _deps(existing_agent=agent)

    result = await GetAgentByIdUseCase(agent_repo).execute(GetAgentInput(agent_id=agent.id))
    assert result is agent

    unknown = uuid4()
    agent_repo.get_by_id.return_value = None
    with pytest.raises(AgentNotFoundError):
        await GetAgentByIdUseCase(agent_repo).execute(GetAgentInput(agent_id=unknown))
