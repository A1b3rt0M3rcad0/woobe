from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.ai_agent_cases import (
    _force_strict_json_settings,
    _resolve_implicit_provider_model_bindings,
)
from modules.agent.domain.entities import Agent, ProviderModel
from modules.agent.domain.enums import Provider, ProviderModelStatus


def test_json_output_settings_are_persisted_as_strict() -> None:
    agent = Agent(
        settings={
            "response_format": {
                "enabled": True,
                "type": "json",
                "strict": False,
                "schema": {"message": "string"},
            }
        }
    )

    _force_strict_json_settings(agent)

    assert agent.settings["response_format"]["strict"] is True


@pytest.mark.asyncio
async def test_implicit_provider_model_binding_is_resolved_before_agent_is_saved() -> None:
    project_id = uuid4()
    credential_id = uuid4()
    provider_model_id = uuid4()
    agent = Agent(
        project_id=project_id,
        provider_credential_id=credential_id,
        provider=Provider.openai,
        model="gpt-4.1-mini",
    )
    provider_model = ProviderModel(
        id=provider_model_id,
        project_id=project_id,
        provider_credential_id=credential_id,
        name="Primary chat model",
        model="gpt-4.1-mini",
        status=ProviderModelStatus.active,
    )
    provider_model_repo = MagicMock()
    provider_model_repo.list_by_credential = AsyncMock(return_value=[provider_model])

    await _resolve_implicit_provider_model_bindings(agent, provider_model_repo)

    assert agent.provider_model_id == provider_model_id
    provider_model_repo.list_by_credential.assert_awaited_once_with(credential_id)


@pytest.mark.asyncio
async def test_implicit_binding_ignores_inactive_or_embedding_models() -> None:
    project_id = uuid4()
    credential_id = uuid4()
    agent = Agent(
        project_id=project_id,
        provider_credential_id=credential_id,
        provider=Provider.openai,
        model="text-embedding-3-small",
    )
    inactive = ProviderModel(
        project_id=project_id,
        provider_credential_id=credential_id,
        name="Inactive chat model",
        model="text-embedding-3-small",
        status=ProviderModelStatus.inactive,
    )
    embedding = ProviderModel(
        project_id=project_id,
        provider_credential_id=credential_id,
        name="Embedding model",
        model="text-embedding-3-small",
        status=ProviderModelStatus.active,
        metadata={"capability": "embedding"},
    )
    provider_model_repo = MagicMock()
    provider_model_repo.list_by_credential = AsyncMock(return_value=[inactive, embedding])

    await _resolve_implicit_provider_model_bindings(agent, provider_model_repo)

    assert agent.provider_model_id is None
