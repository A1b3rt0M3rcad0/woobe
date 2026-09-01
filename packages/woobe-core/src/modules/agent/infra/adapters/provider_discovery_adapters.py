from __future__ import annotations

from typing import Any

from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
)
from modules.agent.infra.adapters.model_discovery import (
    ModelDiscoveryContext,
    ModelDiscoveryService,
)
from modules.agent.infra.adapters.openrouter_embedding_discovery import (
    OpenRouterEmbeddingModelDiscoveryService,
)
from shared.contracts.errors import ValidationError
from shared.infra.crypto import decrypt_secret


class ProviderModelDiscoveryAdapter:
    def __init__(self, service: ModelDiscoveryService) -> None:
        self._service = service

    async def __call__(
        self,
        provider: str,
        api_key: str,
        metadata: dict[str, Any],
    ) -> list[AvailableProviderModelOutput]:
        return await self._service.list_models(
            ModelDiscoveryContext(
                provider=provider,
                api_key=api_key,
                metadata=metadata,
            )
        )


class EmbeddingModelDiscoveryAdapter:
    def __init__(self, service: OpenRouterEmbeddingModelDiscoveryService) -> None:
        self._service = service

    async def __call__(
        self,
        _provider: str,
        api_key: str,
        metadata: dict[str, Any],
    ) -> list[AvailableProviderModelOutput]:
        return await self._service.list_models(
            api_key=api_key,
            metadata=metadata,
        )


class ProviderSecretResolver:
    def __init__(self, encryption_key: str) -> None:
        self._encryption_key = encryption_key

    def __call__(self, encrypted_secret: str) -> str:
        return decrypt_secret(encrypted_secret, self._encryption_key)


class ProviderCredentialValidator:
    def __init__(self, discovery: ModelDiscoveryService) -> None:
        self._discovery = discovery

    async def __call__(
        self,
        provider: str,
        secret: str,
        metadata: dict[str, Any],
    ) -> None:
        try:
            models = await self._discovery.list_models(
                ModelDiscoveryContext(
                    provider=provider,
                    api_key=secret,
                    metadata=metadata,
                )
            )
        except Exception as exc:
            raise ValidationError(
                f"Unable to verify the new provider API key: {exc}"
            ) from exc
        if not models:
            raise ValidationError(
                "Unable to verify the new provider API key: provider returned no models"
            )
