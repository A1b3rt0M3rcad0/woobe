from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from modules.agent.application.provider_registry import (
    ProviderAdapter,
    ProviderConnection,
    ProviderManifest,
    ProviderRegistry,
)
from modules.agent.domain.model_spec import (
    ModelCapability,
    ModelCapabilityNames,
    ModelInteractionSpec,
    ModelLimits,
    ModelModalities,
    ModelOperations,
    ModelSpec,
    ModelTypes,
)
from modules.agent.infra.adapters.model_discovery import (
    ModelDiscoveryContext,
    ModelDiscoveryService,
)


OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class ProviderAdapterError(RuntimeError):
    pass


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _positive_int(*values: Any) -> int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def _json_get(
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: int = 20,
) -> dict[str, Any]:
    request = UrlRequest(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Woobe/0.14.0",
            **dict(headers),
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ProviderAdapterError(
            f"Provider request failed with HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise ProviderAdapterError(
            f"Provider request failed: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise ProviderAdapterError("Provider request timed out") from exc

    try:
        result = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProviderAdapterError(
            "Provider returned invalid JSON"
        ) from exc
    if not isinstance(result, dict):
        raise ProviderAdapterError(
            "Provider returned an unsupported response"
        )
    return result


async def _async_json_get(
    url: str,
    *,
    headers: Mapping[str, str],
) -> dict[str, Any]:
    return await asyncio.to_thread(_json_get, url, headers=headers)


def _connection_base_url(
    connection: ProviderConnection,
    default: str,
) -> str:
    return (
        connection.base_url
        or str(connection.metadata.get("base_url") or "")
        or default
    ).strip().rstrip("/")


def _language_spec(
    *,
    provider: str,
    model_id: str,
    display_name: str,
    input_modalities: set[str] | frozenset[str] | None = None,
    output_modalities: set[str] | frozenset[str] | None = None,
    context_window: int | None = None,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
    capabilities: Mapping[str, ModelCapability] | None = None,
    raw: Mapping[str, Any] | None = None,
    source: str = "provider",
) -> ModelSpec:
    return ModelSpec(
        provider=provider,
        model_id=model_id,
        display_name=display_name,
        model_type=ModelTypes.LANGUAGE,
        operations=frozenset({ModelOperations.LANGUAGE_GENERATE}),
        input_modalities=frozenset(
            input_modalities or {ModelModalities.TEXT}
        ),
        output_modalities=frozenset(
            output_modalities or {ModelModalities.TEXT}
        ),
        interaction=ModelInteractionSpec(
            mode="conversation",
            supports_conversation=True,
            supports_history=True,
            supports_system_instruction=True,
            supports_context_injection=True,
        ),
        capabilities=dict(capabilities or {}),
        limits=ModelLimits(
            context_window=context_window,
            max_input_tokens=max_input_tokens,
            max_output_tokens=max_output_tokens,
        ),
        default_model_strategy=ModelOperations.LANGUAGE_GENERATE,
        source=source,
        metadata={"provider_model_raw": dict(raw or {})},
    )


def _embedding_spec(
    *,
    provider: str,
    model_id: str,
    display_name: str,
    max_input_tokens: int | None = None,
    raw: Mapping[str, Any] | None = None,
    source: str = "provider",
) -> ModelSpec:
    return ModelSpec(
        provider=provider,
        model_id=model_id,
        display_name=display_name,
        model_type=ModelTypes.EMBEDDING,
        operations=frozenset({ModelOperations.EMBEDDING_CREATE}),
        input_modalities=frozenset({ModelModalities.TEXT}),
        output_modalities=frozenset({ModelModalities.EMBEDDING}),
        interaction=ModelInteractionSpec(
            mode="isolated",
            supports_batch=True,
        ),
        capabilities={},
        limits=ModelLimits(max_input_tokens=max_input_tokens),
        default_model_strategy=ModelOperations.EMBEDDING_CREATE,
        source=source,
        metadata={"provider_model_raw": dict(raw or {})},
    )


def _modality_set(
    values: Any,
    *,
    default: set[str],
) -> set[str]:
    if not isinstance(values, list):
        return set(default)
    normalized = {
        str(value).strip().lower()
        for value in values
        if str(value).strip()
    }
    return normalized or set(default)


def _common_discovery_capabilities(item: Any) -> dict[str, ModelCapability]:
    capabilities: dict[str, ModelCapability] = {}
    if isinstance(getattr(item, "supports_tools", None), bool):
        capabilities[ModelCapabilityNames.TOOL_CALLING] = ModelCapability(
            supported=bool(item.supports_tools),
            source="provider",
        )
    if isinstance(getattr(item, "supports_json", None), bool):
        capabilities[
            ModelCapabilityNames.STRUCTURED_OUTPUT
        ] = ModelCapability(
            supported=bool(item.supports_json),
            config=(
                {"formats": ["json_object"]}
                if item.supports_json
                else {}
            ),
            source="provider",
        )
    if isinstance(getattr(item, "supports_streaming", None), bool):
        capabilities[ModelCapabilityNames.STREAMING] = ModelCapability(
            supported=bool(item.supports_streaming),
            source="provider",
        )
    return capabilities


class _DiscoveryServiceProviderAdapter:
    provider_key: str
    discovery_provider_key: str

    def __init__(
        self,
        manifest: ProviderManifest,
        discovery: ModelDiscoveryService | None = None,
    ) -> None:
        self._manifest = manifest
        self._discovery = discovery or ModelDiscoveryService()

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    async def validate_connection(
        self,
        connection: ProviderConnection,
    ) -> None:
        models = await self.discover_models(connection)
        if not models:
            raise ProviderAdapterError(
                f"Provider {self.manifest.key} returned no models"
            )

    async def discover_models(
        self,
        connection: ProviderConnection,
    ) -> tuple[ModelSpec, ...]:
        metadata = dict(connection.metadata)
        if connection.base_url:
            metadata["base_url"] = connection.base_url
        items = await self._discovery.list_models(
            ModelDiscoveryContext(
                provider=self.discovery_provider_key,
                api_key=connection.api_key,
                metadata=metadata,
            )
        )
        return tuple(self._normalize_item(item) for item in items)

    def _normalize_item(self, item: Any) -> ModelSpec:
        raw = _mapping(getattr(item, "raw", None))
        architecture = _mapping(raw.get("architecture"))
        input_modalities = _modality_set(
            raw.get("input_modalities")
            or architecture.get("input_modalities"),
            default={ModelModalities.TEXT},
        )
        output_modalities = _modality_set(
            raw.get("output_modalities")
            or architecture.get("output_modalities"),
            default={ModelModalities.TEXT},
        )
        model_id = str(item.id)
        display_name = str(item.label or item.id)

        explicit_type = str(
            raw.get("model_type")
            or raw.get("type")
            or ""
        ).strip().lower()
        is_embedding = (
            explicit_type in {"embedding", "embeddings"}
            or "embed" in model_id.lower()
        )
        if is_embedding:
            return _embedding_spec(
                provider=self.provider_key,
                model_id=model_id,
                display_name=display_name,
                max_input_tokens=getattr(item, "context_window", None),
                raw=raw,
            )

        return _language_spec(
            provider=self.provider_key,
            model_id=model_id,
            display_name=display_name,
            input_modalities=input_modalities,
            output_modalities=output_modalities,
            context_window=getattr(item, "context_window", None),
            max_output_tokens=getattr(item, "max_output_tokens", None),
            capabilities=_common_discovery_capabilities(item),
            raw=raw,
        )


class OpenAIProviderAdapter(_DiscoveryServiceProviderAdapter):
    provider_key = "openai"
    discovery_provider_key = "openai"

    def __init__(self, discovery: ModelDiscoveryService | None = None) -> None:
        super().__init__(
            ProviderManifest(
                key="openai",
                display_name="OpenAI",
                protocols=frozenset(
                    {"openai.chat_completions", "openai.responses"}
                ),
                supports_discovery=True,
            ),
            discovery,
        )


class OpenAICompatibleProviderAdapter(_DiscoveryServiceProviderAdapter):
    provider_key = "openai_compatible"
    discovery_provider_key = "custom"

    def __init__(self, discovery: ModelDiscoveryService | None = None) -> None:
        super().__init__(
            ProviderManifest(
                key="openai_compatible",
                display_name="OpenAI Compatible",
                protocols=frozenset(
                    {"openai.chat_completions"}
                ),
                supports_discovery=True,
                metadata_schema={
                    "base_url": {"type": "string", "required": True},
                },
            ),
            discovery,
        )


class OpenRouterProviderAdapter(_DiscoveryServiceProviderAdapter):
    provider_key = "openrouter"
    discovery_provider_key = "openrouter"

    def __init__(self, discovery: ModelDiscoveryService | None = None) -> None:
        super().__init__(
            ProviderManifest(
                key="openrouter",
                display_name="OpenRouter",
                protocols=frozenset(
                    {"openai.chat_completions"}
                ),
                supports_discovery=True,
            ),
            discovery,
        )


class AnthropicProviderAdapter:
    def __init__(self) -> None:
        self._manifest = ProviderManifest(
            key="anthropic",
            display_name="Anthropic",
            protocols=frozenset({"anthropic.messages"}),
            supports_discovery=True,
        )

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    async def validate_connection(
        self,
        connection: ProviderConnection,
    ) -> None:
        models = await self.discover_models(connection)
        if not models:
            raise ProviderAdapterError("Anthropic returned no models")

    async def discover_models(
        self,
        connection: ProviderConnection,
    ) -> tuple[ModelSpec, ...]:
        base_url = _connection_base_url(connection, ANTHROPIC_BASE_URL)
        payload = await _async_json_get(
            f"{base_url}/v1/models?limit=1000",
            headers={
                "X-Api-Key": connection.api_key,
                "anthropic-version": str(
                    connection.metadata.get("anthropic_version")
                    or "2023-06-01"
                ),
            },
        )
        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            raise ProviderAdapterError(
                "Anthropic model discovery response has no data array"
            )

        result: list[ModelSpec] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            model_id = str(raw.get("id") or "").strip()
            if not model_id:
                continue
            raw_capabilities = _mapping(raw.get("capabilities"))
            capabilities: dict[str, ModelCapability] = {
                ModelCapabilityNames.TOOL_CALLING: ModelCapability(
                    supported=True,
                    source="provider_catalog",
                ),
                ModelCapabilityNames.STREAMING: ModelCapability(
                    supported=True,
                    source="provider_catalog",
                ),
            }

            structured = _mapping(
                raw_capabilities.get("structured_outputs")
            )
            if "supported" in structured:
                capabilities[
                    ModelCapabilityNames.STRUCTURED_OUTPUT
                ] = ModelCapability(
                    supported=bool(structured.get("supported")),
                    config={"formats": ["json_schema"]},
                    source="provider",
                )

            thinking = _mapping(raw_capabilities.get("thinking"))
            effort = _mapping(raw_capabilities.get("effort"))
            reasoning_supported = bool(
                thinking.get("supported")
                or effort.get("supported")
            )
            if thinking or effort:
                levels = [
                    name
                    for name, value in effort.items()
                    if name != "supported"
                    and isinstance(value, dict)
                    and value.get("supported") is True
                ]
                capabilities[ModelCapabilityNames.REASONING] = ModelCapability(
                    supported=reasoning_supported,
                    config={"levels": levels},
                    source="provider",
                )

            batch = _mapping(raw_capabilities.get("batch"))
            if "supported" in batch:
                capabilities[ModelCapabilityNames.BATCH] = ModelCapability(
                    supported=bool(batch.get("supported")),
                    source="provider",
                )

            citations = _mapping(raw_capabilities.get("citations"))
            if "supported" in citations:
                capabilities[
                    ModelCapabilityNames.CITATIONS
                ] = ModelCapability(
                    supported=bool(citations.get("supported")),
                    source="provider",
                )

            code_execution = _mapping(
                raw_capabilities.get("code_execution")
            )
            if "supported" in code_execution:
                capabilities[
                    ModelCapabilityNames.CODE_EXECUTION
                ] = ModelCapability(
                    supported=bool(code_execution.get("supported")),
                    source="provider",
                )

            inputs = {ModelModalities.TEXT}
            image_input = _mapping(raw_capabilities.get("image_input"))
            if image_input.get("supported") is True:
                inputs.add(ModelModalities.IMAGE)

            result.append(
                _language_spec(
                    provider="anthropic",
                    model_id=model_id,
                    display_name=str(
                        raw.get("display_name") or model_id
                    ),
                    input_modalities=inputs,
                    output_modalities={ModelModalities.TEXT},
                    context_window=_positive_int(
                        raw.get("max_input_tokens")
                    ),
                    max_input_tokens=_positive_int(
                        raw.get("max_input_tokens")
                    ),
                    max_output_tokens=_positive_int(
                        raw.get("max_tokens")
                    ),
                    capabilities=capabilities,
                    raw=raw,
                )
            )
        return tuple(result)


class DeepSeekProviderAdapter:
    def __init__(self) -> None:
        self._manifest = ProviderManifest(
            key="deepseek",
            display_name="DeepSeek",
            protocols=frozenset(
                {
                    "openai.chat_completions",
                    "openai.responses",
                    "anthropic.messages",
                }
            ),
            supports_discovery=True,
        )

    @property
    def manifest(self) -> ProviderManifest:
        return self._manifest

    async def validate_connection(
        self,
        connection: ProviderConnection,
    ) -> None:
        models = await self.discover_models(connection)
        if not models:
            raise ProviderAdapterError("DeepSeek returned no models")

    async def discover_models(
        self,
        connection: ProviderConnection,
    ) -> tuple[ModelSpec, ...]:
        base_url = _connection_base_url(connection, DEEPSEEK_BASE_URL)
        payload = await _async_json_get(
            f"{base_url}/models",
            headers={
                "Authorization": f"Bearer {connection.api_key}",
            },
        )
        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            raise ProviderAdapterError(
                "DeepSeek model discovery response has no data array"
            )

        result: list[ModelSpec] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            model_id = str(raw.get("id") or "").strip()
            if not model_id:
                continue

            effort = _mapping(raw.get("effort"))
            levels = effort.get("supported_levels")
            capabilities = {
                ModelCapabilityNames.TOOL_CALLING: ModelCapability(
                    supported=True,
                    source="provider_catalog",
                ),
                ModelCapabilityNames.STRUCTURED_OUTPUT: ModelCapability(
                    supported=True,
                    config={"formats": ["json_object"]},
                    source="provider_catalog",
                ),
                ModelCapabilityNames.STREAMING: ModelCapability(
                    supported=True,
                    source="provider_catalog",
                ),
            }
            if isinstance(levels, list):
                capabilities[
                    ModelCapabilityNames.REASONING
                ] = ModelCapability(
                    supported=bool(levels),
                    config={
                        "levels": [
                            str(level)
                            for level in levels
                        ],
                        "default_level": effort.get(
                            "default_level"
                        ),
                    },
                    source="provider",
                )

            result.append(
                _language_spec(
                    provider="deepseek",
                    model_id=model_id,
                    display_name=str(raw.get("name") or model_id),
                    input_modalities=_modality_set(
                        raw.get("input_modalities"),
                        default={ModelModalities.TEXT},
                    ),
                    output_modalities=_modality_set(
                        raw.get("output_modalities"),
                        default={ModelModalities.TEXT},
                    ),
                    context_window=_positive_int(
                        raw.get("context_window")
                    ),
                    max_output_tokens=_positive_int(
                        raw.get("max_output_tokens")
                    ),
                    capabilities=capabilities,
                    raw=raw,
                )
            )
        return tuple(result)


def build_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(OpenAIProviderAdapter())
    registry.register(OpenAICompatibleProviderAdapter())
    registry.register(OpenRouterProviderAdapter())
    registry.register(AnthropicProviderAdapter())
    registry.register(DeepSeekProviderAdapter())

    # Historical custom credentials are OpenAI-compatible endpoints in the current
    # Woobe persistence/API contract. Keep them valid without making custom a second
    # implementation.
    registry.register_alias("custom", "openai_compatible")
    return registry


__all__ = [
    "AnthropicProviderAdapter",
    "DeepSeekProviderAdapter",
    "OpenAICompatibleProviderAdapter",
    "OpenAIProviderAdapter",
    "OpenRouterProviderAdapter",
    "ProviderAdapterError",
    "build_provider_registry",
]
