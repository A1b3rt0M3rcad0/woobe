from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import ListProviderCredentialsInput
from modules.agent.application.use_cases.ai_credential_cases import (
    ListProviderCredentialsUseCase,
)
from modules.agent.domain.entities import Agent, ProviderCredential
from modules.agent.infra.adapters.model_provider_registry import build_provider_registry
from modules.agent.infra.execution.release_runtime_resolver import (
    ReleaseRuntimeResolver,
)
from shared.contracts.errors import ValidationError
from tests.unit.agent.test_model_provider_runtime_regressions import _language_spec


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider,supported",
    [
        ("openai", True),
        ("custom", True),
        ("openai_compatible", True),
        ("openrouter", True),
        ("anthropic", False),
        ("deepseek", False),
    ],
)
async def test_credential_discovery_advertises_implemented_embedding_support(
    provider, supported
):
    credential = ProviderCredential(project_id=uuid4(), provider=provider)
    repository = SimpleNamespace(list_by_project=AsyncMock(return_value=[credential]))
    result = await ListProviderCredentialsUseCase(
        repository, build_provider_registry()
    ).execute(ListProviderCredentialsInput(project_id=credential.project_id))
    assert result[0].supports_embedding is supported


@pytest.mark.parametrize("provider", ["custom", "openai_compatible"])
def test_compatible_runtime_uses_frozen_model_endpoint_and_refuses_missing_endpoint(
    provider,
):
    credential = ProviderCredential(project_id=uuid4(), provider=provider)
    spec = replace(
        _language_spec(),
        provider="openai_compatible",
        metadata={"base_url": "https://frozen.example/v1"},
    )
    agent = Agent(
        project_id=credential.project_id,
        provider=provider,
        model=spec.model_id,
        settings={
            "base_url": "https://mutable.example/v1",
            "model_spec": spec.as_dict(),
            "model_spec_frozen": True,
        },
    )
    resolver = object.__new__(ReleaseRuntimeResolver)
    assert resolver._resolve_base_url(agent, credential) == "https://frozen.example/v1"
    with pytest.raises(ValidationError, match="base_url"):
        resolver._resolve_base_url_for_provider(provider, credential, {})


@pytest.mark.parametrize(
    "endpoint",
    ["relative/path", "ftp://example.test", "https://", "https://example.test:invalid"],
)
def test_invalid_compatible_endpoint_fails_before_invocation(endpoint):
    credential = ProviderCredential(
        project_id=uuid4(),
        provider="openai_compatible",
        metadata={"base_url": endpoint},
    )
    resolver = object.__new__(ReleaseRuntimeResolver)
    with pytest.raises(ValidationError, match="absolute HTTP"):
        resolver._resolve_base_url_for_provider("openai_compatible", credential, {})
