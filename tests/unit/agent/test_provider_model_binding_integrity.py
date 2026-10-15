from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import (
    CreateProviderModelInput,
    UpdateProviderModelInput,
)
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
    UpdateProviderModelUseCase,
)
from modules.agent.domain.entities import Agent, ProviderCredential, ProviderModel
from modules.agent.infra.execution.release_runtime_resolver import (
    ReleaseRuntimeResolver,
)
from shared.contracts.errors import ValidationError
from modules.agent.application.model_spec_definition import parse_model_spec_definition
from tests.unit.agent.test_model_provider_runtime_regressions import _language_spec


class Models:
    def __init__(self, item=None):
        self.item = item
        self.writes = 0

    async def get_by_id(self, identifier):
        return deepcopy(self.item) if self.item and identifier == self.item.id else None

    async def save(self, item):
        self.item = deepcopy(item)
        self.writes += 1
        return item

    update = save


class Credentials:
    def __init__(self, item):
        self.item = item

    async def get_by_id(self, identifier):
        return self.item if identifier == self.item.id else None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [("provider", "anthropic"), ("model_id", "other"), ("model_type", "embedding")],
)
async def test_create_rejects_mismatched_spec_without_writing(field, value):
    credential = ProviderCredential(project_id=uuid4(), provider="openai")
    spec = _language_spec().as_dict()
    spec[field] = value
    models = Models()
    with pytest.raises(ValidationError):
        await CreateProviderModelUseCase(models, Credentials(credential)).execute(
            CreateProviderModelInput(
                project_id=credential.project_id,
                provider_credential_id=credential.id,
                name="Test",
                model="gpt-test",
                model_type="language",
                spec=spec,
            )
        )
    assert models.writes == 0


@pytest.mark.asyncio
async def test_hash_only_patch_cannot_replace_server_hash():
    credential = ProviderCredential(project_id=uuid4(), provider="openai")
    models = Models()
    creator = CreateProviderModelUseCase(models, Credentials(credential))
    output = await creator.execute(
        CreateProviderModelInput(
            project_id=credential.project_id,
            provider_credential_id=credential.id,
            name="Test",
            model="gpt-test",
            spec=_language_spec().as_dict(),
        )
    )
    with pytest.raises(ValidationError):
        await UpdateProviderModelUseCase(models, Credentials(credential)).execute(
            output.id, UpdateProviderModelInput(spec_hash="forged")
        )
    assert models.item.spec_hash == output.spec_hash


@pytest.mark.asyncio
@pytest.mark.parametrize("fallback", [False, True])
async def test_frozen_runtime_uses_snapshot_and_original_credential(fallback):
    credential = ProviderCredential(project_id=uuid4(), provider="openai")
    model = ProviderModel(
        project_id=credential.project_id,
        provider_credential_id=uuid4(),
        model="retargeted",
    )
    agent = Agent(
        project_id=credential.project_id,
        model="gpt-test",
        provider="openai",
        provider_credential_id=credential.id,
    )
    key = "fallback_model_spec" if fallback else "model_spec"
    agent.settings = {key: _language_spec().as_dict(), f"{key}_frozen": True}
    if fallback:
        agent.fallback_provider_model_id = model.id
        agent.fallback_credential_id = credential.id
        agent.fallback_provider = "openai"
        agent.fallback_model = "gpt-test"
    else:
        agent.provider_model_id = model.id
    resolver = object.__new__(ReleaseRuntimeResolver)
    await resolver._resolve_provider_model_refs(
        SimpleNamespace(
            provider_models=Models(model), provider_credentials=Credentials(credential)
        ),
        agent,
    )
    assert (agent.fallback_model if fallback else agent.model) == "gpt-test"
    assert (
        agent.fallback_credential_id if fallback else agent.provider_credential_id
    ) == credential.id


@pytest.mark.parametrize(
    "change",
    [
        {"surprise": True},
        {"operations": [" "]},
        {"spec_version": 999},
        {"capabilities": {"tool_calling": {"supported": "false"}}},
        {"pricing": {"input_cost_per_1m_tokens": float("nan")}},
        {"pricing": {"output_cost_per_1m_tokens": float("inf")}},
        {"limits": {"context_window": 0}},
    ],
)
def test_authoring_rejects_lossy_or_invalid_spec(change):
    with pytest.raises(ValidationError):
        parse_model_spec_definition({**_language_spec().as_dict(), **change})


def test_custom_alias_is_valid_without_discarding_spec_capabilities():
    credential = ProviderCredential(project_id=uuid4(), provider="custom")
    spec = _language_spec().as_dict()
    spec["provider"] = "openai_compatible"
    proposed = CreateProviderModelUseCase.prepare_definition(
        CreateProviderModelInput(
            project_id=credential.project_id,
            provider_credential_id=credential.id,
            name="Test",
            model="gpt-test",
            spec=spec,
        ),
        credential,
    )
    assert proposed.spec["source"] == "provider"
    assert proposed.spec["capabilities"]["tool_calling"]["supported"] is True


@pytest.mark.asyncio
async def test_retarget_requires_matching_spec_and_drops_old_overrides():
    from dataclasses import replace

    credential = ProviderCredential(project_id=uuid4(), provider="openai")
    repositories = Models(), Credentials(credential)
    creator = CreateProviderModelUseCase(*repositories)
    output = await creator.execute(
        CreateProviderModelInput(
            project_id=credential.project_id,
            provider_credential_id=credential.id,
            name="Model",
            model="gpt-test",
            spec=_language_spec().as_dict(),
            metadata={
                "model_spec_overrides": {"capabilities": {"tool_calling": False}}
            },
        )
    )
    updater = UpdateProviderModelUseCase(*repositories)
    for patch in ({"model": "new-model"}, {"spec": None}):
        with pytest.raises(ValidationError):
            await updater.execute(output.id, UpdateProviderModelInput(**patch))
        assert repositories[0].item.spec_hash == output.spec_hash
    updated = await updater.execute(
        output.id,
        UpdateProviderModelInput(
            model="new-model",
            spec=replace(_language_spec(), model_id="new-model").as_dict(),
        ),
    )
    assert updated.spec["model_id"] == "new-model"
    assert updated.spec["capabilities"]["tool_calling"]["supported"] is True
    assert updated.metadata["model_spec_overrides"] == {}
