from __future__ import annotations

from typing import Any, Mapping

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
from shared.contracts.llm_cost import provider_model_pricing_snapshot


def _value(value: Any) -> str | None:
    if value is None:
        return None
    resolved = value.value if hasattr(value, "value") else value
    text = str(resolved).strip()
    return text or None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def legacy_provider_model_is_embedding(provider_model: Any) -> bool:
    """Compatibility-only inference for records created before ModelSpec existed.

    New domain/runtime code must use ModelSpec.model_type/operations. Name inference
    intentionally lives here so it can be removed after persisted specs are backfilled.
    """

    metadata = _mapping(getattr(provider_model, "metadata", None))
    explicit = _value(
        metadata.get("model_type")
        or metadata.get("capability")
        or metadata.get("type")
    )
    if explicit is not None:
        normalized = explicit.lower()
        if normalized in {"embedding", "embeddings"}:
            return True
        if normalized in {
            "generation",
            "language",
            "llm",
            "chat",
            "chat_completion",
        }:
            return False

    value = (
        f"{getattr(provider_model, 'name', '')} "
        f"{getattr(provider_model, 'model', '')}"
    ).lower()
    return "embed" in value


class LegacyModelSpecResolver:
    """Materialize a ModelSpec from the current ProviderModel persistence shape."""

    def resolve(
        self,
        provider_model: Any,
        *,
        provider: str | None = None,
    ) -> ModelSpec:
        metadata = _mapping(getattr(provider_model, "metadata", None))

        persisted_spec = metadata.get("model_spec")
        if isinstance(persisted_spec, Mapping):
            return ModelSpec.from_dict(persisted_spec)

        provider_key = (
            _value(provider)
            or _value(metadata.get("provider"))
            or "unknown"
        )
        model_id = _value(getattr(provider_model, "model", None)) or ""
        display_name = (
            _value(getattr(provider_model, "name", None))
            or model_id
        )

        snapshot = provider_model_pricing_snapshot(
            provider_model_id=getattr(provider_model, "id", None),
            provider_credential_id=getattr(
                provider_model,
                "provider_credential_id",
                None,
            ),
            provider=provider_key,
            model=model_id,
            metadata=metadata,
        )

        if legacy_provider_model_is_embedding(provider_model):
            return self._embedding_spec(
                provider_key=provider_key,
                model_id=model_id,
                display_name=display_name,
                metadata=metadata,
                snapshot=snapshot,
            )

        return self._language_spec(
            provider_key=provider_key,
            model_id=model_id,
            display_name=display_name,
            metadata=metadata,
            snapshot=snapshot,
        )

    @staticmethod
    def _capabilities(
        snapshot: Mapping[str, Any],
    ) -> dict[str, ModelCapability]:
        source = _value(snapshot.get("capability_source")) or "legacy"
        capabilities: dict[str, ModelCapability] = {}

        supports_tools = snapshot.get("supports_tools")
        if isinstance(supports_tools, bool):
            capabilities[ModelCapabilityNames.TOOL_CALLING] = ModelCapability(
                supported=supports_tools,
                source=source,
            )

        supports_json = snapshot.get("supports_json")
        if isinstance(supports_json, bool):
            capabilities[
                ModelCapabilityNames.STRUCTURED_OUTPUT
            ] = ModelCapability(
                supported=supports_json,
                config=(
                    {"formats": ["json_object"]}
                    if supports_json
                    else {}
                ),
                source=source,
            )

        supports_streaming = snapshot.get("supports_streaming")
        if isinstance(supports_streaming, bool):
            capabilities[ModelCapabilityNames.STREAMING] = ModelCapability(
                supported=supports_streaming,
                source=source,
            )
        return capabilities

    def _language_spec(
        self,
        *,
        provider_key: str,
        model_id: str,
        display_name: str,
        metadata: Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> ModelSpec:
        return ModelSpec(
            provider=provider_key,
            model_id=model_id,
            display_name=display_name,
            model_type=ModelTypes.LANGUAGE,
            operations=frozenset({ModelOperations.LANGUAGE_GENERATE}),
            input_modalities=frozenset({ModelModalities.TEXT}),
            output_modalities=frozenset({ModelModalities.TEXT}),
            interaction=ModelInteractionSpec(
                mode="conversation",
                supports_conversation=True,
                supports_history=True,
                supports_system_instruction=True,
                supports_context_injection=True,
            ),
            capabilities=self._capabilities(snapshot),
            limits=ModelLimits(
                context_window=snapshot.get("context_window"),
                max_output_tokens=snapshot.get("max_output_tokens"),
            ),
            default_model_strategy=ModelOperations.LANGUAGE_GENERATE,
            source="legacy",
            metadata={
                "compatibility_mode": "legacy",
                "capability_source": snapshot.get("capability_source"),
                "provider_model_metadata": dict(metadata),
            },
        )

    def _embedding_spec(
        self,
        *,
        provider_key: str,
        model_id: str,
        display_name: str,
        metadata: Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> ModelSpec:
        dimensions = metadata.get("dimensions")
        return ModelSpec(
            provider=provider_key,
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
            limits=ModelLimits(
                max_input_tokens=snapshot.get("context_window"),
            ),
            default_model_strategy=ModelOperations.EMBEDDING_CREATE,
            source="legacy",
            metadata={
                "compatibility_mode": "legacy",
                "dimensions": dimensions,
                "provider_model_metadata": dict(metadata),
            },
        )


__all__ = [
    "LegacyModelSpecResolver",
    "legacy_provider_model_is_embedding",
]
