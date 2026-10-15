"""One baseline plus explicit overrides; legacy null means no override."""

from copy import deepcopy
from dataclasses import replace

from modules.agent.application.model_spec_definition import (
    validate_pricing,
    parse_model_spec_definition,
)
from modules.agent.domain.model_spec import ModelCapability, ModelLimits, ModelSpec
from shared.contracts.errors import ValidationError

LEGACY_CAPABILITIES = {
    "supports_tools": "tool_calling",
    "supports_json": "structured_output",
    "supports_streaming": "streaming",
}


def compose_model_spec(
    spec: ModelSpec, metadata: dict, *, previous_metadata=None
) -> ModelSpec:
    previous = previous_metadata or {}
    baseline = (
        metadata.get("model_spec_baseline")
        or previous.get("model_spec_baseline")
        or spec.as_dict()
    )
    if not isinstance(baseline, dict):
        raise ValidationError("ModelSpec baseline must be an object")
    baseline_spec = parse_model_spec_definition(baseline)
    if (
        baseline_spec.model_id != spec.model_id
        or baseline_spec.provider != spec.provider
    ):
        raise ValidationError("ModelSpec baseline identity differs from Model")
    overrides = deepcopy(previous.get("model_spec_overrides") or {})
    patch = metadata.get("model_spec_overrides") or {}
    if not isinstance(patch, dict) or patch.keys() - {
        "capabilities",
        "limits",
        "pricing",
    }:
        raise ValidationError("Invalid ModelSpec override groups")
    # Adapt legacy inputs at the boundary, never establish a second precedence path.
    legacy = {"capabilities": {}, "limits": {}, "pricing": {}}
    for old, key in LEGACY_CAPABILITIES.items():
        value = (metadata.get("capabilities") or {}).get(old)
        if value is not None:
            if type(value) is not bool:
                raise ValidationError("Capability overrides must be boolean")
            legacy["capabilities"][key] = value
    for key in ("context_window", "max_output_tokens"):
        if metadata.get(key) is not None:
            legacy["limits"][key] = metadata[key]
    legacy["pricing"] = {
        key: value
        for key, value in (metadata.get("pricing") or {}).items()
        if value is not None
        and key
        in {
            "input_cost_per_1m_tokens",
            "output_cost_per_1m_tokens",
            "currency",
            "billing_unit",
        }
    }
    for group in legacy:
        supplied = patch.get(group, {})
        if not isinstance(supplied, dict):
            raise ValidationError("ModelSpec override group must be an object")
        target = overrides.setdefault(group, {})
        for key, value in {**legacy[group], **supplied}.items():
            if (
                isinstance(value, dict)
                and value.get("action") in {"inherit", "clear"}
                and set(value) == {"action"}
            ):
                target.pop(key, None)
            elif value is None:
                raise ValidationError(
                    "Use inherit or unknown explicitly instead of null in ModelSpec overrides"
                )
            else:
                target[key] = value
    capabilities = dict(baseline_spec.capabilities)
    for key, value in overrides.get("capabilities", {}).items():
        if value == "unknown":
            capabilities.pop(key, None)
        elif type(value) is bool:
            old = capabilities.get(key)
            capabilities[key] = ModelCapability(
                value, config=dict(old.config) if old else {}, source="manual"
            )
        else:
            raise ValidationError(
                "Capability override must be true, false, unknown or inherit"
            )
    limits = baseline_spec.limits.as_dict()
    for key, value in overrides.get("limits", {}).items():
        if key not in limits or type(value) is not int or value <= 0:
            raise ValidationError("Limit overrides must be positive integers")
        limits[key] = value
    pricing = validate_pricing(
        {**baseline_spec.pricing, **overrides.get("pricing", {})}
    )
    metadata["model_spec_baseline"] = deepcopy(baseline)
    metadata["model_spec_overrides"] = {
        key: value for key, value in overrides.items() if value
    }
    runtime_metadata = dict(baseline_spec.metadata)
    if metadata.get("base_url"):
        runtime_metadata["base_url"] = metadata["base_url"]
    if metadata.get("dimensions") is not None:
        runtime_metadata["dimensions"] = metadata["dimensions"]
    return replace(
        baseline_spec,
        capabilities=capabilities,
        limits=ModelLimits(**limits),
        pricing=pricing,
        metadata=runtime_metadata,
    )
