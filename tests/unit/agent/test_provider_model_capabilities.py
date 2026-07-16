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
