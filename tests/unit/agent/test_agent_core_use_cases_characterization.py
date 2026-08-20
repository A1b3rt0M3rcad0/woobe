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


def _passthrough(method):
    async def _call(value):
        return value

    setattr(method, "side_effect", _call)


def _core_dependencies(*, existing_agent=None, credential=None, provider_model=None):
    agent_repo = SimpleNamespace(
        save=AsyncMock(),
        update=AsyncMock(),
        get_by_id=AsyncMock(return_value=existing_agent),
        list_by_project=AsyncMock(return_value=[]),
    )
    _passthrough(agent_repo.save)
    _passthrough(agent_repo.update)

    credential_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=credential),
    )
    provider_model_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=provider_model),
        list_by_credential=AsyncMock(return_value=[]),
    )
    outbox = SimpleNamespace(write=AsyncMock())
    return agent_repo, credential_repo, provider_model_repo, outbox


@pytest.mark.asyncio
async def test_create_agent_persists_and_emits_created_event():
    project_id = uuid4()
    agent_repo, credential_repo, _, outbox = _core_dependencies()
    use_case = CreateAgentUseCase(agent_repo, credential_repo, outbox)

    saved = await use_case.execute(
        CreateAgentInput(
            project_id=project_id,
            name="Support Agent",
            model="gpt-test",
            provider=Provider.openai,
        )
    )

    assert saved.project_id == project_id
    assert saved.name == "Support Agent"
    assert saved.model == "gpt-test"
    agent_repo.save.assert_awaited_once()
    outbox.write.assert_awaited_once()
    event = outbox.write.await_args.args[0]
    assert event.agent_id == saved.id


@pytest.mark.asyncio
async def test_create_agent_forces_strict_json_when_json_response_is_enabled():
    project_id = uuid4()
    agent_repo, credential_repo, _, outbox = _core_dependencies()
    use_case = CreateAgentUseCase(agent_repo, credential_repo, outbox)

    saved = await use_case.execute(
        CreateAgentInput(
            project_id=project_id,
            name="JSON Agent",
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

    assert saved.settings["response_format"]["strict"] is True


@pytest.mark.asyncio
async def test_create_agent_does_not_force_strict_for_disabled_json_contract():
    project_id = uuid4()
    agent_repo, credential_repo, _, outbox = _core_dependencies()
    use_case = CreateAgentUseCase(agent_repo, credential_repo, outbox)

    saved = await use_case.execute(
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
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies(
        credential=credential,
        provider_model=provider_model,
    )
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    saved = await use_case.execute(
        CreateAgentInput(
            project_id=project_id,
            provider_model_id=provider_model.id,
            name="Resolved Agent",
            model="client-supplied-model-is-not-authoritative",
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
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies(
        credential=credential,
        provider_model=first,
    )
    provider_model_repo.list_by_credential.return_value = [second, first]
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    saved = await use_case.execute(
        CreateAgentInput(
            project_id=project_id,
            provider_credential_id=credential.id,
            name="Implicit Binding",
            model="shared-model",
        )
    )

    assert saved.provider_model_id == first.id
    assert saved.model == first.model


@pytest.mark.asyncio
async def test_implicit_binding_ignores_embedding_provider_models():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    embedding = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        model="text-embedding-3-small",
        metadata={"capability": "embedding"},
    )
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies(
        credential=credential,
    )
    provider_model_repo.list_by_credential.return_value = [embedding]
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    saved = await use_case.execute(
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
async def test_explicit_embedding_provider_model_is_rejected_for_agent_runtime():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    embedding = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        metadata={"type": "embeddings"},
    )
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies(
        credential=credential,
        provider_model=embedding,
    )
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    with pytest.raises(ConflictError, match="not compatible with agent runtime"):
        await use_case.execute(
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
    provider_model = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
        status=ProviderModelStatus.inactive,
    )
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies(
        credential=credential,
        provider_model=provider_model,
    )
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    with pytest.raises(ValidationError, match="Provider model must be active"):
        await use_case.execute(
            CreateAgentInput(
                project_id=project_id,
                provider_model_id=provider_model.id,
                name="Inactive Model",
                model="ignored",
            )
        )


@pytest.mark.asyncio
async def test_missing_explicit_provider_model_is_rejected():
    project_id = uuid4()
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies()
    provider_model_repo.get_by_id.return_value = None
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    with pytest.raises(ModelConfigNotFoundError):
        await use_case.execute(
            CreateAgentInput(
                project_id=project_id,
                provider_model_id=uuid4(),
                name="Missing Model",
                model="ignored",
            )
        )


@pytest.mark.asyncio
async def test_missing_direct_provider_credential_is_rejected():
    project_id = uuid4()
    agent_repo, credential_repo, _, outbox = _core_dependencies(credential=None)
    credential_id = uuid4()
    use_case = CreateAgentUseCase(agent_repo, credential_repo, outbox)

    with pytest.raises(CredentialNotFoundError):
        await use_case.execute(
            CreateAgentInput(
                project_id=project_id,
                provider_credential_id=credential_id,
                name="Missing Credential",
                model="gpt-test",
            )
        )

    agent_repo.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_provider_credential_is_rejected_for_provider_model_binding():
    project_id = uuid4()
    credential = _credential(
        project_id=project_id,
        status=CredentialStatus.revoked,
    )
    provider_model = _provider_model(
        project_id=project_id,
        credential_id=credential.id,
    )
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies(
        credential=credential,
        provider_model=provider_model,
    )
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    with pytest.raises(ValidationError, match="Provider credential must be active"):
        await use_case.execute(
            CreateAgentInput(
                project_id=project_id,
                provider_model_id=provider_model.id,
                name="Revoked Credential",
                model="ignored",
            )
        )


@pytest.mark.asyncio
async def test_fallback_provider_model_binding_is_resolved_independently():
    project_id = uuid4()
    primary_credential = _credential(project_id=project_id)
    fallback_credential = _credential(project_id=project_id)
    fallback_model = _provider_model(
        project_id=project_id,
        credential_id=fallback_credential.id,
        model="fallback-model",
    )
    agent_repo, credential_repo, provider_model_repo, outbox = _core_dependencies()
    provider_model_repo.get_by_id.return_value = fallback_model

    async def credential_by_id(credential_id):
        if credential_id == fallback_credential.id:
            return fallback_credential
        if credential_id == primary_credential.id:
            return primary_credential
        return None

    credential_repo.get_by_id.side_effect = credential_by_id
    use_case = CreateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        provider_model_repo,
    )

    saved = await use_case.execute(
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
async def test_update_agent_fails_when_agent_does_not_exist():
    project_id = uuid4()
    agent_repo, credential_repo, _, outbox = _core_dependencies(existing_agent=None)
    use_case = UpdateAgentUseCase(agent_repo, credential_repo, outbox)

    with pytest.raises(AgentNotFoundError):
        await use_case.execute(uuid4(), UpdateAgentInput(name="new name"))

    agent_repo.update.assert_not_awaited()
    outbox.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_blocks_deactivation_while_network_drafts_reference_agent():
    project_id = uuid4()
    existing = _agent(project_id=project_id, status=AgentStatus.active)
    agent_repo, credential_repo, _, outbox = _core_dependencies(existing_agent=existing)
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
async def test_update_allows_deactivation_when_no_network_draft_references_exist():
    project_id = uuid4()
    existing = _agent(project_id=project_id, status=AgentStatus.active)
    agent_repo, credential_repo, _, outbox = _core_dependencies(existing_agent=existing)
    reader = SimpleNamespace(list_draft_references=AsyncMock(return_value=[]))
    use_case = UpdateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        network_usage_reader=reader,
    )

    result = await use_case.execute(
        existing.id,
        UpdateAgentInput(status=AgentStatus.inactive),
    )

    assert result.status == AgentStatus.inactive
    agent_repo.update.assert_awaited_once()
    outbox.write.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_agent_forces_strict_json_and_emits_updated_event():
    project_id = uuid4()
    existing = _agent(project_id=project_id)
    agent_repo, credential_repo, _, outbox = _core_dependencies(existing_agent=existing)
    use_case = UpdateAgentUseCase(agent_repo, credential_repo, outbox)

    result = await use_case.execute(
        existing.id,
        UpdateAgentInput(
            name="Updated Agent",
            settings={
                "response_format": {
                    "enabled": True,
                    "type": "json",
                    "strict": False,
                }
            },
        ),
    )

    assert result.name == "Updated Agent"
    assert result.settings["response_format"]["strict"] is True
    outbox.write.assert_awaited_once()
    event = outbox.write.await_args.args[0]
    assert event.agent_id == existing.id


@pytest.mark.asyncio
async def test_list_agents_without_project_is_empty_and_does_not_query_repository():
    agent_repo, _, _, _ = _core_dependencies()

    result = await ListAgentsUseCase(agent_repo).execute(ListAgentsInput(project_id=None))

    assert result == []
    agent_repo.list_by_project.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_agents_maps_repository_entities_to_public_output():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    agent_repo, _, _, _ = _core_dependencies()
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
async def test_get_agent_returns_existing_entity():
    project_id = uuid4()
    agent = _agent(project_id=project_id)
    agent_repo, _, _, _ = _core_dependencies(existing_agent=agent)

    result = await GetAgentByIdUseCase(agent_repo).execute(
        GetAgentInput(agent_id=agent.id)
    )

    assert result is agent
    agent_repo.get_by_id.assert_awaited_once_with(agent.id)


@pytest.mark.asyncio
async def test_get_agent_raises_not_found_for_unknown_id():
    agent_repo, _, _, _ = _core_dependencies(existing_agent=None)
    unknown = uuid4()

    with pytest.raises(AgentNotFoundError):
        await GetAgentByIdUseCase(agent_repo).execute(GetAgentInput(agent_id=unknown))
