from __future__ import annotations

from collections.abc import Awaitable, Callable

from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
    ListAvailableProviderModelsInput,
)
from modules.agent.domain.enums import CredentialStatus
from modules.agent.application.interfaces.repositories import ProviderCredentialRepository
from shared.contracts.errors import ValidationError

ModelDiscoveryCallable = Callable[[str, str, dict], Awaitable[list[AvailableProviderModelOutput]]]
SecretResolverCallable = Callable[[str], str]


def _is_embedding_model(model: AvailableProviderModelOutput) -> bool:
    value = f"{model.id} {model.label}".lower()
    return "embed" in value


class ListAvailableProviderModelsUseCase:
    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        discovery: ModelDiscoveryCallable,
        embedding_discovery: ModelDiscoveryCallable,
        resolve_secret: SecretResolverCallable,
    ) -> None:
        self._credential_repo = credential_repo
        self._discovery = discovery
        self._embedding_discovery = embedding_discovery
        self._resolve_secret = resolve_secret

    async def execute(self, input_dto: ListAvailableProviderModelsInput) -> list[AvailableProviderModelOutput]:
        credential = await self._credential_repo.get_by_id(input_dto.credential_id)
        if credential is None:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(input_dto.credential_id)
        if input_dto.project_id and credential.project_id != input_dto.project_id:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(input_dto.credential_id)
        if getattr(credential.status, "value", credential.status) != CredentialStatus.active.value:
            raise ValidationError("Provider credential must be active to discover models")

        provider = credential.provider.value if hasattr(credential.provider, "value") else str(credential.provider)
        metadata = credential.metadata or {}
        capability = (input_dto.capability or "").strip().lower()
        if capability == "embeddings":
            capability = "embedding"
        if capability not in {"", "embedding", "generation"}:
            raise ValidationError(f"Unsupported model discovery capability: {capability}")

        try:
            api_key = self._resolve_secret(credential.encrypted_secret)
        except Exception as exc:
            raise ValidationError("Provider credential secret could not be resolved. Recreate the credential.") from exc

        try:
            if capability == "embedding" and provider == "openrouter":
                return await self._embedding_discovery(provider, api_key, metadata)
            models = await self._discovery(provider, api_key, metadata)
        except Exception as exc:
            raise ValidationError(str(exc)) from exc

        if capability == "embedding":
            return [model for model in models if _is_embedding_model(model)]
        if capability == "generation":
            return [model for model in models if not _is_embedding_model(model)]
        return models
