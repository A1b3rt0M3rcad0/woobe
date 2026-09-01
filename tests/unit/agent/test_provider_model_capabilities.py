import asyncio
from types import SimpleNamespace
from uuid import uuid4

from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
    ListAvailableProviderModelsInput,
)
from modules.agent.application.use_cases.ai_agent_cases import _is_embedding_provider_model
from modules.agent.application.use_cases.list_available_provider_models import (
    ListAvailableProviderModelsUseCase,
)
from modules.agent.infra.adapters.model_discovery import ModelDiscoveryService
from shared.contracts.llm_cost import provider_model_pricing_snapshot


def _available(model_id: str, label: str) -> AvailableProviderModelOutput:
    return AvailableProviderModelOutput(
        id=model_id,
        label=label,
        provider="openai",
    )


def test_agent_model_capability_prefers_explicit_metadata() -> None:
    explicit_embedding = SimpleNamespace(
        name="Knowledge model",
        model="custom-model",
        metadata={"capability": "embedding"},
    )
    explicit_generation = SimpleNamespace(
        name="Embedding proxy name",
        model="embed-proxy",
        metadata={"capability": "generation"},
    )
    legacy_embedding = SimpleNamespace(
        name="Text Embedding 3 Small",
        model="text-embedding-3-small",
        metadata={},
    )

    assert _is_embedding_provider_model(explicit_embedding) is True
    assert _is_embedding_provider_model(explicit_generation) is False
    assert _is_embedding_provider_model(legacy_embedding) is True


def test_generation_discovery_excludes_embedding_models() -> None:
    project_id = uuid4()
    credential_id = uuid4()
    credential = SimpleNamespace(
        id=credential_id,
        project_id=project_id,
        provider="openai",
        status="active",
        metadata={},
        encrypted_secret="encrypted",
    )

    class CredentialRepository:
        async def get_by_id(self, requested_id):
            return credential if requested_id == credential_id else None

    async def discovery(_provider, _api_key, _metadata):
        return [
            _available("gpt-4.1-mini", "GPT-4.1 Mini"),
            _available("text-embedding-3-small", "Text Embedding 3 Small"),
        ]

    use_case = ListAvailableProviderModelsUseCase(
        credential_repo=CredentialRepository(),
        discovery=discovery,
        embedding_discovery=discovery,
        resolve_secret=lambda _encrypted: "secret",
    )

    result = asyncio.run(
        use_case.execute(
            ListAvailableProviderModelsInput(
                credential_id=credential_id,
                project_id=project_id,
                capability="generation",
            )
        )
    )

    assert [item.id for item in result] == ["gpt-4.1-mini"]


def test_openrouter_discovery_separates_context_window_from_output_limit() -> None:
    models = ModelDiscoveryService()._normalize_openrouter(
        {
            "data": [
                {
                    "id": "provider/model",
                    "name": "Provider Model",
                    "context_length": 131072,
                    "top_provider": {"max_completion_tokens": 8192},
                    "supported_parameters": ["tools", "response_format"],
                    "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                }
            ]
        }
    )

    model = models[0]
    assert model.context_window == 131072
    assert model.max_output_tokens == 8192
    assert model.supports_tools is True
    assert model.supports_json is True
    assert model.supports_streaming is True


def test_custom_discovery_uses_only_explicit_provider_limits() -> None:
    models = ModelDiscoveryService()._normalize_openai(
        {
            "data": [
                {
                    "id": "custom-model",
                    "context_window": "65536",
                    "max_output_tokens": "4096",
                }
            ]
        },
        provider="custom",
    )

    model = models[0]
    assert model.context_window == 65536
    assert model.max_output_tokens == 4096


def test_provider_model_manual_capabilities_are_carried_to_runtime_snapshot() -> None:
    snapshot = provider_model_pricing_snapshot(
        provider_model_id=uuid4(),
        provider_credential_id=uuid4(),
        provider="custom",
        model="deepseek-v4-flash",
        metadata={
            "context_window": 128000,
            "max_output_tokens": 8192,
            "capability_source": "manual",
            "capabilities": {
                "supports_tools": True,
                "supports_json": False,
                "supports_streaming": True,
            },
        },
    )

    assert snapshot["context_window"] == 128000
    assert snapshot["max_output_tokens"] == 8192
    assert snapshot["supports_tools"] is True
    assert snapshot["supports_json"] is False
    assert snapshot["supports_streaming"] is True
    assert snapshot["capability_source"] == "manual"


def test_output_limit_is_never_used_as_context_window() -> None:
    snapshot = provider_model_pricing_snapshot(
        provider_model_id=uuid4(),
        provider_credential_id=uuid4(),
        provider="openrouter",
        model="provider/model",
        metadata={
            "provider_model_raw": {
                "top_provider": {"max_completion_tokens": 8192},
            }
        },
    )

    assert snapshot["context_window"] is None
    assert snapshot["max_output_tokens"] == 8192
