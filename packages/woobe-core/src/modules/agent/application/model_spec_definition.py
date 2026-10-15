"""Authoring invariants shared by CRUD, inspection and reconciliation.

Historical deserialization remains in ModelSpec.from_dict; writes additionally use
the native portable validator so malformed input cannot be silently discarded.
"""

from dataclasses import replace
from math import isfinite

from modules.agent.application.portable_model_spec import validate_portable_model_spec
from modules.agent.domain.model_spec import ModelSpec, ModelOperations, model_spec_hash
from modules.agent.domain.provider_identity import (
    canonical_provider_key,
    validate_model_spec_binding,
    validate_provider_base_url,
)
from shared.contracts.errors import ValidationError


def validate_pricing(pricing: dict) -> dict:
    result = dict(pricing)
    for key in ("input_cost_per_1m_tokens", "output_cost_per_1m_tokens"):
        value = result.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            raise ValidationError("Model prices must be finite nonnegative numbers")
        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValidationError(
                "Model prices must be finite nonnegative numbers"
            ) from exc
        if not isfinite(number) or number < 0:
            raise ValidationError("Model prices must be finite nonnegative numbers")
        result[key] = number
    currency = result.get("currency")
    if currency is not None and currency not in {
        "USD",
        "EUR",
        "BRL",
        "GBP",
        "JPY",
        "CAD",
        "AUD",
        "CNY",
        "CHF",
    }:
        raise ValidationError(
            "Model pricing currency must be a supported ISO currency code"
        )
    if result.get("billing_unit") not in (None, "per_1m_tokens"):
        raise ValidationError("Normalized token pricing must use per_1m_tokens")
    return result


def parse_model_spec_definition(value: dict) -> ModelSpec:
    def finite_json(item):
        if isinstance(item, dict):
            for nested in item.values():
                finite_json(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                finite_json(nested)
        elif isinstance(item, float) and not isfinite(item):
            raise ValidationError("ModelSpec numbers must be finite")

    finite_json(value)
    validate_portable_model_spec(value)
    dimensions = (value.get("metadata") or {}).get("dimensions")
    if dimensions is not None and (type(dimensions) is not int or dimensions <= 0):
        raise ValidationError("Embedding dimensions must be a positive integer")
    endpoint = (value.get("metadata") or {}).get("base_url")
    if endpoint is not None:
        try:
            validate_provider_base_url(endpoint)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
    for key in ("operations", "input_modalities", "output_modalities"):
        if not value.get(key) or not all(item.strip() for item in value[key]):
            raise ValidationError(f"ModelSpec {key} must not be empty")
    for capability in (value.get("capabilities") or {}).values():
        if (
            isinstance(capability, dict)
            and type(capability.get("supported")) is not bool
        ):
            raise ValidationError("Model capability support must be boolean")
    try:
        spec = ModelSpec.from_dict(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValidationError(f"Invalid ModelSpec: {exc}") from exc
    spec = replace(
        spec,
        provider=canonical_provider_key(spec.provider),
        model_id=spec.model_id.strip(),
        model_type=spec.model_type.strip().lower(),
        pricing=validate_pricing(dict(spec.pricing)),
    )
    required_type = {
        ModelOperations.LANGUAGE_GENERATE: "language",
        ModelOperations.EMBEDDING_CREATE: "embedding",
        ModelOperations.IMAGE_GENERATE: "image",
        ModelOperations.AUDIO_TRANSCRIBE: "audio",
        ModelOperations.AUDIO_SYNTHESIZE: "audio",
        ModelOperations.VIDEO_GENERATE: "video",
        ModelOperations.RERANK: "rerank",
        ModelOperations.REALTIME_SESSION: "realtime",
    }
    for operation in spec.operations:
        if operation in required_type and spec.model_type != required_type[operation]:
            raise ValidationError("ModelSpec identity type differs from its operations")
    if spec.model_type == "embedding" and (
        ModelOperations.EMBEDDING_CREATE not in spec.operations
        or "embedding" not in spec.output_modalities
    ):
        raise ValidationError(
            "Embedding ModelSpec requires embedding.create and embedding output"
        )
    if spec.model_type == "language" and (
        ModelOperations.LANGUAGE_GENERATE not in spec.operations
        or "text" not in spec.output_modalities
    ):
        raise ValidationError(
            "Language ModelSpec requires language.generate and text output"
        )
    return spec



def validate_spec_assertions(spec, *, spec_hash=None, spec_version=None):
    if (spec_hash is not None and spec_hash != model_spec_hash(spec)) or (
        spec_version is not None and spec_version != spec.spec_version
    ):
        raise ValidationError(
            "ModelSpec hash/version assertion differs from the server definition"
        )
