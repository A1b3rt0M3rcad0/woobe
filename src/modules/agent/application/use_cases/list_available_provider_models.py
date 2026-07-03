from __future__ import annotations

from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
    ListAvailableProviderModelsInput,
)
from modules.agent.domain.enums import CredentialStatus
from modules.agent.domain.repositories import ProviderCredentialRepository
from modules.agent.infra.adapters.model_discovery import (
    ModelDiscoveryContext,
    ModelDiscoveryService,
    ProviderModelDiscoveryError,
)
from modules.agent.infra.adapters.openrouter_embedding_discovery import OpenRouterEmbeddingModelDiscoveryService
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret
from shared.infra.errors import ValidationError


def _is_embedding_model(model: AvailableProviderModelOutput) -> bool:
    value = f"{model.id} {model.label}".lower()
    return "embed" in value


class ListAvailableProviderModelsUseCase:
    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        discovery_service: ModelDiscoveryService | None = None,
        embedding_discovery_service: OpenRouterEmbeddingModelDiscoveryService | None = None,
        encryption_key: str | None = None,
    ) -> None:
        self._credential_repo = credential_repo
        self._discovery_service = discovery_service or ModelDiscoveryService()
        self._embedding_discovery_service = embedding_discovery_service or OpenRouterEmbeddingModelDiscoveryService()
        self._encryption_key = encryption_key or Settings().encryption_key

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
        if capability not in {"", "embedding"}:
            raise ValidationError(f"Unsupported model discovery capability: {capability}")

        try:
            api_key = decrypt_secret(credential.encrypted_secret, self._encryption_key)
        except Exception as exc:
            raise ValidationError("Provider credential secret could not be decrypted. Recreate the credential.") from exc

        try:
            if capability == "embedding" and provider == "openrouter":
                return await self._embedding_discovery_service.list_models(
                    api_key=api_key,
                    metadata=metadata,
                )

            models = await self._discovery_service.list_models(
                ModelDiscoveryContext(
                    provider=provider,
                    api_key=api_key,
                    metadata=metadata,
                )
            )
            if capability == "embedding":
                return [model for model in models if _is_embedding_model(model)]
            return models
        except ProviderModelDiscoveryError as exc:
            raise ValidationError(str(exc)) from exc
