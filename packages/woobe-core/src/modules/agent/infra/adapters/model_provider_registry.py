from __future__ import annotations

from dataclasses import replace
from modules.agent.application.interfaces.provider_registry import UnclassifiedProviderModel
from modules.agent.infra.adapters.openai_model_enrichment import OPENAI_MODEL_EVIDENCE, REVISION

import asyncio
import json
from math import isfinite
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from modules.agent.application.interfaces.provider_registry import (
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
        if isinstance(value, float) and (not isfinite(value) or not value.is_integer()):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError, OverflowError):
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
        raise ProviderAdapterError(
            f"Provider request failed with HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise ProviderAdapterError(
            f"Provider request failed: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise ProviderAdapterError("Provider request timed out") from exc

    try:
        result = json.loads(payload, parse_constant=lambda _value: None)
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
    pricing: Mapping[str, Any] | None = None,
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
        pricing=dict(pricing or {}),
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
    pricing: Mapping[str, Any] | None = None,
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
        pricing=dict(pricing or {}),
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
    return normalized


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
                {"formats": ["json_object", "json_schema"] if "structured_outputs" in (_mapping(getattr(item, "raw", None)).get("supported_parameters") or []) else ["json_object"]}
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
        original = _mapping(getattr(item, "raw", None))
        enrichment = OPENAI_MODEL_EVIDENCE.get(str(item.id), {}) if self.provider_key == "openai" else {}
        raw = {**enrichment, **original}
        architecture = _mapping(raw.get("architecture"))
        inputs = _modality_set(raw.get("input_modalities", architecture.get("input_modalities")), default=set())
        outputs = _modality_set(raw.get("output_modalities", architecture.get("output_modalities")), default=set())
        explicit_type = raw.get("model_type") or raw.get("type")
        explicit_ops = raw.get("operations") or []
        if explicit_type == "audio" and "audio" in inputs and "text" in outputs:
            explicit_ops = ["audio.transcribe"]
        operation_families = {"audio.transcribe": "audio", "audio.synthesize": "audio", "image.generate": "image",
            "video.generate": "video", "rerank": "rerank", "realtime.session": "realtime"}
        for operation in explicit_ops:
            if operation in operation_families and inputs and outputs:
                return ModelSpec(provider=self.provider_key, model_id=str(item.id), display_name=str(item.label or item.id),
                    model_type=operation_families[operation], operations=frozenset({operation}),
                    input_modalities=frozenset(inputs), output_modalities=frozenset(outputs),
                    interaction=ModelInteractionSpec(mode="isolated"), source="provider", metadata={"provider_model_raw": original})
        if explicit_type in {"embedding", "embeddings"} or "embedding.create" in explicit_ops or "embedding" in outputs:
            spec = _embedding_spec(provider=self.provider_key, model_id=str(item.id), display_name=str(item.label or item.id),
                max_input_tokens=item.context_window, raw=original,
                pricing={"input_cost_per_1m_tokens": item.input_cost_per_1m_tokens,
                    "output_cost_per_1m_tokens": item.output_cost_per_1m_tokens,
                    "currency": "USD", "billing_unit": "per_1m_tokens"})
            if raw.get("dimensions") is not None:
                spec = replace(spec, metadata={**spec.metadata, "dimensions": raw["dimensions"]})
            return spec
        if explicit_type in {"language", "generation", "chat"} or "language.generate" in explicit_ops:
            inputs = inputs or {"text"}
            outputs = outputs or {"text"}
        if "text" in inputs and "text" in outputs and explicit_type not in {"audio", "image", "video", "rerank"}:
            caps = _common_discovery_capabilities(item)
            for old, key in {"supports_tools": "tool_calling", "supports_json": "structured_output", "supports_streaming": "streaming"}.items():
                if key not in caps and type(enrichment.get(old)) is bool:
                    caps[key] = ModelCapability(enrichment[old], source="curated")
            spec = _language_spec(provider=self.provider_key, model_id=str(item.id), display_name=str(item.label or item.id),
                input_modalities=inputs, output_modalities=outputs,
                context_window=item.context_window or enrichment.get("context_window"),
                max_output_tokens=item.max_output_tokens or enrichment.get("max_output_tokens"),
                capabilities=caps, raw=original,
                pricing={"input_cost_per_1m_tokens": item.input_cost_per_1m_tokens,
                    "output_cost_per_1m_tokens": item.output_cost_per_1m_tokens,
                    "currency": "USD", "billing_unit": "per_1m_tokens"})
            if enrichment:
                spec = replace(spec, metadata={**spec.metadata, "enrichment_revision": REVISION,
                    "enrichment_source": "https://platform.openai.com/docs/models/" + str(item.id)})
            return spec
        families = {"image": ("image", "image.generate"), "audio": ("audio", "audio.synthesize"),
            "video": ("video", "video.generate"), "scores": ("rerank", "rerank")}
        for modality, (family, operation) in families.items():
            if modality in outputs and inputs:
                return ModelSpec(provider=self.provider_key, model_id=str(item.id), display_name=str(item.label or item.id),
                    model_type=family, operations=frozenset({operation}), input_modalities=frozenset(inputs),
                    output_modalities=frozenset(outputs), interaction=ModelInteractionSpec(mode="isolated"),
                    source="provider", metadata={"provider_model_raw": original})
        return UnclassifiedProviderModel(self.provider_key, str(item.id), str(item.label or item.id), original)


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
                supported_operations=frozenset({ModelOperations.LANGUAGE_GENERATE, ModelOperations.EMBEDDING_CREATE}),
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
                supported_operations=frozenset({ModelOperations.LANGUAGE_GENERATE, ModelOperations.EMBEDDING_CREATE}),
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
                supported_operations=frozenset({ModelOperations.LANGUAGE_GENERATE, ModelOperations.EMBEDDING_CREATE}),
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
        from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential, configuration_get_json
        from urllib.parse import urlencode
        raw_items = []
        seen_cursors = set()
        seen_ids = set()
        cursor = None
        for page in range(50):
            query = {"limit": 1000}
            if cursor is not None:
                query["after_id"] = cursor
            url = f"{base_url}/v1/models?{urlencode(query)}"
            headers = {"anthropic-version": str(connection.metadata.get("anthropic_version") or "2023-06-01")}
            payload = (await configuration_get_json(url, connection.api_key, header="X-Api-Key", prefix="", headers=headers)
                if isinstance(connection.api_key, BoundConfigurationCredential) else await _async_json_get(url,
                    headers={**headers, "X-Api-Key": connection.api_key}))
            items = payload.get("data")
            if not isinstance(items, list):
                raise ProviderAdapterError("Anthropic model discovery response has no data array")
            for item in items:
                if isinstance(item, dict) and item.get("id") and item["id"] not in seen_ids:
                    raw_items.append(item)
                    seen_ids.add(item["id"])
            if payload.get("has_more") is not True:
                break
            cursor = payload.get("last_id")
            if not isinstance(cursor, str) or not cursor or cursor in seen_cursors:
                raise ProviderAdapterError("Anthropic model pagination made no progress")
            seen_cursors.add(cursor)
        else:
            raise ProviderAdapterError("Anthropic model pagination exceeded the page limit")
        raw_items.sort(key=lambda item: item["id"])

        result: list[ModelSpec] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            model_id = str(raw.get("id") or "").strip()
            if not model_id:
                continue
            raw_capabilities = _mapping(raw.get("capabilities"))
            capabilities: dict[str, ModelCapability] = {}

            structured = _mapping(
                raw_capabilities.get("structured_outputs")
            )
            if type(structured.get("supported")) is bool:
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
            if type(thinking.get("supported")) is bool or type(effort.get("supported")) is bool:
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
            if type(batch.get("supported")) is bool:
                capabilities[ModelCapabilityNames.BATCH] = ModelCapability(
                    supported=bool(batch.get("supported")),
                    source="provider",
                )

            citations = _mapping(raw_capabilities.get("citations"))
            if type(citations.get("supported")) is bool:
                capabilities[
                    ModelCapabilityNames.CITATIONS
                ] = ModelCapability(
                    supported=bool(citations.get("supported")),
                    source="provider",
                )

            code_execution = _mapping(
                raw_capabilities.get("code_execution")
            )
            if type(code_execution.get("supported")) is bool:
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
        from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential, configuration_get_json
        payload = await configuration_get_json(f"{base_url}/models", connection.api_key) if isinstance(connection.api_key, BoundConfigurationCredential) else await _async_json_get(
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
            raw_caps = _mapping(raw.get("capabilities"))
            capabilities = {}
            # Only the protocol selected by Woobe supplies execution capabilities.
            protocols = _mapping(raw.get("api_capabilities"))
            openai_caps = _mapping(protocols.get("openai_chat_completions") or protocols.get("openai.chat_completions"))
            for native, key in {"tool_calling": ModelCapabilityNames.TOOL_CALLING,
                    "structured_output": ModelCapabilityNames.STRUCTURED_OUTPUT,
                    "streaming": ModelCapabilityNames.STREAMING}.items():
                flag = openai_caps.get(native, raw_caps.get(native))
                flag = flag.get("supported") if isinstance(flag, dict) else flag
                if type(flag) is bool:
                    capabilities[key] = ModelCapability(flag, source="provider")
            if isinstance(levels, list) and all(isinstance(level, str) and level.strip() for level in levels):
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

            known_language = model_id in {"deepseek-chat", "deepseek-reasoner"}
            inputs = _modality_set(raw.get("input_modalities"), default={"text"} if known_language else set())
            outputs = _modality_set(raw.get("output_modalities"), default={"text"} if known_language else set())
            if "text" not in inputs or "text" not in outputs:
                result.append(UnclassifiedProviderModel("deepseek", model_id, str(raw.get("name") or model_id), raw))
                continue
            constraints = {}
            for protocol, evidence in protocols.items():
                if isinstance(evidence, dict) and evidence.get("system_prompt_update") in {"leading-only", "in-history"}:
                    constraints[protocol] = {"system_prompt_update": evidence["system_prompt_update"]}
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
            result[-1] = replace(result[-1], metadata={**result[-1].metadata,
                "runtime_constraints": constraints, "protocol": "openai.chat_completions"})
        return tuple(result)


def build_provider_registry(discovery=None) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(OpenAIProviderAdapter(discovery))
    registry.register(OpenAICompatibleProviderAdapter(discovery))
    registry.register(OpenRouterProviderAdapter(discovery))
    registry.register(AnthropicProviderAdapter())
    registry.register(DeepSeekProviderAdapter())

    # Historical custom credentials are OpenAI-compatible endpoints in the current
    # Woobe persistence/API contract. Keep them valid without making custom a second
    # implementation.
    from modules.agent.domain.provider_identity import PROVIDER_ALIASES
    for alias, target in PROVIDER_ALIASES.items():
        registry.register_alias(alias, target)
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
