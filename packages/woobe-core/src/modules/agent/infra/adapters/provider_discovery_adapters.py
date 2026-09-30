from __future__ import annotations

from typing import Any

from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
)
from modules.agent.application.interfaces.provider_registry import ProviderConnection
from modules.agent.domain.model_spec import (
    ModelCapabilityNames,
    ModelSpec,
)
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
from shared.contracts.errors import ValidationError
from shared.infra.crypto import decrypt_secret


def _capability_supported(
    spec: ModelSpec,
    name: str,
) -> bool | None:
    capability = spec.capability(name)
    return capability.supported if capability is not None else None


def _spec_to_available_output(
    spec: ModelSpec,
    *,
    provider: str,
) -> AvailableProviderModelOutput:
    pricing = dict(spec.pricing or {})
    metadata = dict(spec.metadata or {})
    raw = metadata.get("provider_model_raw")
    return AvailableProviderModelOutput(
        id=spec.model_id,
        label=spec.display_name,
        provider=provider,
        source=spec.source,
        owned_by=(
            str(raw.get("owned_by"))
            if isinstance(raw, dict) and raw.get("owned_by")
            else None
        ),
        context_window=(
            spec.limits.context_window
            or spec.limits.max_input_tokens
        ),
        max_output_tokens=spec.limits.max_output_tokens,
        input_cost_per_1m_tokens=pricing.get(
            "input_cost_per_1m_tokens"
        ),
        output_cost_per_1m_tokens=pricing.get(
            "output_cost_per_1m_tokens"
        ),
        supports_tools=_capability_supported(
            spec,
            ModelCapabilityNames.TOOL_CALLING,
        ),
        supports_json=_capability_supported(
            spec,
            ModelCapabilityNames.STRUCTURED_OUTPUT,
        ),
        supports_streaming=_capability_supported(
            spec,
            ModelCapabilityNames.STREAMING,
        ),
        model_type=spec.model_type,
        operations=sorted(spec.operations),
        input_modalities=sorted(spec.input_modalities),
        output_modalities=sorted(spec.output_modalities),
        capabilities={
            name: capability.as_dict()
            for name, capability in spec.capabilities.items()
        },
        raw={
            **(raw if isinstance(raw, dict) else {}),
            "woobe_model_spec": spec.as_dict(),
        },
    )


class ProviderModelDiscoveryAdapter:
    def __init__(self, service: ModelDiscoveryService) -> None:
        self._service = service
        self._registry = build_provider_registry()

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
        except Exception as exc:
            raise ValidationError(
                f"Unable to verify the new provider API key: {exc}"
            ) from exc
        if not models:
            raise ValidationError(
                "Unable to verify the new provider API key: provider returned no models"
            )
