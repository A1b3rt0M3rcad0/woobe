from __future__ import annotations

from typing import Any

from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
)
from modules.agent.application.interfaces.provider_registry import ProviderConnection
from modules.agent.infra.adapters.model_discovery import (
    ModelDiscoveryContext,
    ModelDiscoveryService,
)
from modules.agent.infra.adapters.model_provider_registry import (
    build_provider_registry,
)
from modules.agent.infra.adapters.openrouter_embedding_discovery import (
    OpenRouterEmbeddingModelDiscoveryService,
)
from modules.agent.infra.adapters.model_discovery_output import _spec_to_available_output
from shared.contracts.errors import ValidationError
from shared.infra.crypto import decrypt_secret



class ProviderModelDiscoveryAdapter:
    def __init__(self, service: ModelDiscoveryService) -> None:
        self._service = service
        self._registry = build_provider_registry(service)

    async def __call__(
        self,
        provider: str,
        api_key: str,
        metadata: dict[str, Any],
    ) -> list[AvailableProviderModelOutput]:
        if self._registry.contains(provider):
            adapter = self._registry.resolve(provider)
            specs = await adapter.discover_models(
                ProviderConnection(
                    provider=self._registry.canonical_key(provider),
                    api_key=api_key,
                    base_url=(
                        str(metadata.get("base_url")).strip()
                        if metadata.get("base_url")
                        else None
                    ),
                    metadata=metadata,
                )
            )
            return [
                _spec_to_available_output(
                    spec,
                    provider=provider,
                )
                for spec in specs
            ]

        # Compatibility fallback for historical provider identifiers that have not
        # received a first-class ProviderAdapter yet.
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
        self._registry = build_provider_registry()

    async def __call__(
        self,
        provider: str,
        secret: str,
        metadata: dict[str, Any],
    ) -> None:
        try:
            if self._registry.contains(provider):
                adapter = self._registry.resolve(provider)
                await adapter.validate_connection(
                    ProviderConnection(
                        provider=self._registry.canonical_key(provider),
                        api_key=secret,
                        base_url=(
                            str(metadata.get("base_url")).strip()
                            if metadata.get("base_url")
                            else None
                        ),
                        metadata=metadata,
                    )
                )
                return

            models = await self._discovery.list_models(
                ModelDiscoveryContext(
                    provider=provider,
                    api_key=secret,
                    metadata=metadata,
                )
            )
        except Exception:
            raise ValidationError("Unable to verify the new provider API key") from None
        if not models:
            raise ValidationError(
                "Unable to verify the new provider API key: provider returned no models"
            )
