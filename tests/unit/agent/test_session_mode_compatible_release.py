from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreateReleaseInput
from modules.agent.application.use_cases.session_mode_compatible_release import (
    SessionModeCompatibleCreateReleaseUseCase,
)
from modules.agent.domain.enums import AgentStatus, Provider, SessionMode


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_saving_draft_adopts_updated_native_model_prices(fallback) -> None:
    from modules.agent.application.dtos.ai_dtos import UpdateProviderModelInput
    from modules.agent.application.use_cases.ai_provider_model_cases import (
        UpdateProviderModelUseCase,
    )
    from modules.agent.application.model_spec_compatibility import (
        LegacyModelSpecResolver,
    )
    from modules.agent.domain.entities import Agent, ProviderCredential, ProviderModel
    from modules.agent.domain.model_spec import ModelSpec, model_spec_hash
    from modules.agent.infra.execution.release_runtime_resolver import (
        ReleaseRuntimeResolver,
    )
    from shared.contracts.llm_cost import calculate_llm_cost

    credential = ProviderCredential(project_id=uuid4(), provider=Provider.custom)
    model = ProviderModel(
        project_id=credential.project_id,
        provider_credential_id=credential.id,
        name="generation",
        model="test",
    )
    old_spec = LegacyModelSpecResolver().resolve(model, provider="custom").as_dict()
    agent = Agent(
        project_id=credential.project_id,
        name="Support",
        provider=Provider.custom,
        model="test",
        provider_model_id=model.id,
        provider_credential_id=credential.id,
        settings={"model_spec": old_spec},
    )
    if fallback:
        agent.fallback_provider_model_id = model.id
        agent.fallback_credential_id = credential.id
        agent.fallback_provider = Provider.custom
        agent.fallback_model = "test"
        agent.settings["fallback_model_spec"] = deepcopy(old_spec)
    models = SimpleNamespace(
        get_by_id=AsyncMock(return_value=model),
        update=AsyncMock(side_effect=lambda item: item),
    )
    credentials = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))
    updated = await UpdateProviderModelUseCase(models, credentials).execute(
        model.id,
        UpdateProviderModelInput(
            metadata={
                "pricing": {
                    "input_cost_per_1m_tokens": 1,
                    "output_cost_per_1m_tokens": 2,
                    "currency": "USD",
                }
            }
        ),
    )
    assert updated.spec["pricing"]["input_cost_per_1m_tokens"] == 1
    assert agent.settings["model_spec"]["pricing"]["input_cost_per_1m_tokens"] is None
    agents = SimpleNamespace(
        get_by_id=AsyncMock(return_value=agent),
        update=AsyncMock(side_effect=lambda item: item),
    )
    delegate = SimpleNamespace(
        execute=AsyncMock(side_effect=lambda item, **kwargs: item)
    )
    saver = SessionModeCompatibleCreateReleaseUseCase(
        delegate, agents, provider_model_repo=models, credential_repo=credentials
    )
    saved = await saver.execute(
        CreateReleaseInput(
            project_id=agent.project_id, agent_id=agent.id, version="draft"
        )
    )
    assert saved.model_spec_snapshot == updated.spec
    assert saved.model_spec_hash == model_spec_hash(ModelSpec.from_dict(updated.spec))
    assert agent.settings["model_spec"] == updated.spec
    if fallback:
        assert saved.fallback_model_spec_snapshot == updated.spec
        assert agent.settings["fallback_model_spec"] == updated.spec
    # Pricing is consumed from the newly saved exact snapshot, not today's catalog.
    execution = deepcopy(agent)
    execution.settings["model_spec_frozen"] = True
    ReleaseRuntimeResolver.__new__(ReleaseRuntimeResolver)._restore_frozen_pricing(
        execution
    )
    result = calculate_llm_cost(
        input_tokens=1000,
        output_tokens=500,
        pricing_snapshot=execution.settings["model_pricing"],
    )
    assert result["cost_usd"] == 0.002 and result["cost_status"] == "known"
    assert (
        old_spec["pricing"]["input_cost_per_1m_tokens"] is None
    )  # Existing captures are unchanged.


@pytest.mark.asyncio
async def test_explicit_imported_snapshot_is_not_replaced_by_current_native_model() -> (
    None
):
    from modules.agent.domain.entities import Agent
    from modules.agent.application.model_spec_compatibility import (
        LegacyModelSpecResolver,
    )
    from modules.agent.domain.model_spec import ModelSpec, model_spec_hash

    agent = Agent(
        project_id=uuid4(),
        name="Imported",
        provider=Provider.custom,
        model="test",
        provider_model_id=uuid4(),
    )
    spec = (
        LegacyModelSpecResolver()
        .resolve(
            SimpleNamespace(
                id=None,
                model="test",
                name="test",
                metadata={
                    "pricing": {
                        "input_cost_per_1m_tokens": 1,
                        "output_cost_per_1m_tokens": 2,
                    }
                },
            ),
            provider="custom",
        )
        .as_dict()
    )
    models = SimpleNamespace(get_by_id=AsyncMock())
    credentials = SimpleNamespace(get_by_id=AsyncMock())
    agents = SimpleNamespace(
        get_by_id=AsyncMock(return_value=agent), update=AsyncMock(return_value=agent)
    )
    delegate = SimpleNamespace(
        execute=AsyncMock(side_effect=lambda item, **kwargs: item)
    )
    saver = SessionModeCompatibleCreateReleaseUseCase(
        delegate, agents, provider_model_repo=models, credential_repo=credentials
    )
    digest = model_spec_hash(ModelSpec.from_dict(spec))
    saved = await saver.execute(
        CreateReleaseInput(
            project_id=agent.project_id,
            agent_id=agent.id,
            version="draft",
            model_spec_snapshot=spec,
            model_spec_hash=digest,
        )
    )
    assert saved.model_spec_snapshot == spec and saved.model_spec_hash == digest
    models.get_by_id.assert_not_awaited()
    credentials.get_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_draft_refresh_rejects_a_model_from_another_project_before_writing() -> (
    None
):
    from modules.agent.domain.entities import Agent, ProviderModel
    from modules.agent.domain.errors import ModelConfigNotFoundError

    agent = Agent(
        project_id=uuid4(),
        name="Support",
        provider=Provider.custom,
        model="test",
        provider_model_id=uuid4(),
    )
    models = SimpleNamespace(
        get_by_id=AsyncMock(return_value=ProviderModel(project_id=uuid4()))
    )
    agents = SimpleNamespace(
        get_by_id=AsyncMock(return_value=agent), update=AsyncMock()
    )
    delegate = SimpleNamespace(execute=AsyncMock())
    saver = SessionModeCompatibleCreateReleaseUseCase(
        delegate,
        agents,
        provider_model_repo=models,
        credential_repo=SimpleNamespace(get_by_id=AsyncMock()),
    )
    with pytest.raises(ModelConfigNotFoundError):
        await saver.execute(
            CreateReleaseInput(
                project_id=agent.project_id, agent_id=agent.id, version="draft"
            )
        )
    delegate.execute.assert_not_awaited()
    agents.update.assert_not_awaited()
    assert agent.settings == {}


@pytest.mark.asyncio
async def test_save_draft_synchronizes_server_canonical_runtime_config_to_agent() -> (
    None
):
    project_id = uuid4()
    agent_id = uuid4()
    skill_id = uuid4()
    skill_version_id = uuid4()
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        name="Calculator",
        description="",
        system_prompt="Old prompt",
        provider=Provider.custom,
        model="deepseek-v4-flash",
        provider_credential_id=uuid4(),
        provider_model_id=uuid4(),
        fallback_provider=None,
        fallback_model=None,
        fallback_credential_id=None,
        fallback_provider_model_id=None,
        temperature=0.7,
        max_output_tokens=2048,
        session_mode=SessionMode.stateless,
        status=AgentStatus.active,
        settings={"runtime_config": {"legacy": True}},
    )
    requested_runtime = {
        "skills": {
            "bindings": [
                {
                    "skill_id": str(skill_id),
                    "skill_version_id": str(skill_version_id),
                    "enabled": True,
                }
            ],
            "snapshots": [],
        }
    }
    canonical_runtime = {
        **requested_runtime,
        "skills": {
            **requested_runtime["skills"],
            "snapshots": [
                {
                    "skill_id": str(skill_id),
                    "skill_version_id": str(skill_version_id),
                    "project_id": str(project_id),
                    "version": "1.0.0",
                    "package_hash": "server-frozen-hash",
                    "package": {"name": "calculate-method"},
                }
            ],
        },
    }
    saved_draft = SimpleNamespace(
        name="Calculator",
        description="Uses the saved Draft",
        system_prompt="Follow installed procedures.",
        response_format={"enabled": False, "type": "text"},
        provider="custom",
        model="deepseek-v4-flash",
        provider_credential_id=agent.provider_credential_id,
        provider_model_id=agent.provider_model_id,
        fallback_provider=None,
        fallback_model=None,
        fallback_credential_id=None,
        fallback_provider_model_id=None,
        base_url="https://provider.example/v1",
        temperature=0.2,
        max_output_tokens=1024,
        session_mode="stateless",
        agent_status="active",
        knowledge_version_id=None,
        runtime_config=canonical_runtime,
    )

    agent_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=agent),
        update=AsyncMock(return_value=agent),
    )
    delegate = SimpleNamespace(execute=AsyncMock(return_value=saved_draft))
    use_case = SessionModeCompatibleCreateReleaseUseCase(delegate, agent_repo)
    input_dto = CreateReleaseInput(
        project_id=project_id,
        agent_id=agent_id,
        version="draft",
        description="Uses the saved Draft",
        system_prompt="Follow installed procedures.",
        runtime_config=requested_runtime,
    )

    result = await use_case.execute(input_dto)

    delegated_input = delegate.execute.await_args.args[0]
    assert delegated_input.runtime_config == requested_runtime
    assert delegated_input.provider == "custom"
    assert delegated_input.model == "deepseek-v4-flash"
    assert delegated_input.session_mode == "stateless"
    assert result is saved_draft
    assert agent.settings["runtime_config"] == canonical_runtime
    assert agent.settings["base_url"] == "https://provider.example/v1"
    assert agent.system_prompt == "Follow installed procedures."
    agent_repo.update.assert_awaited_once_with(agent)
