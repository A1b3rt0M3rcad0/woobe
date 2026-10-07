"""Reject ModelSpec fields that the native compatibility parser would discard."""

from dataclasses import fields as dataclass_fields

from modules.agent.domain.model_spec import (
    MODEL_SPEC_VERSION,
    ModelSpec,
    ModelCapability,
    ModelInteractionSpec,
    ModelLimits,
)
from shared.contracts.errors import ValidationError


def validate_portable_model_spec(value):
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValidationError("Portable ModelSpec must be an object")
    allowed = {field.name for field in dataclass_fields(ModelSpec)}
    if value.keys() - allowed:
        raise ValidationError("Portable ModelSpec contains unsupported fields")
    if "spec_version" in value and (
        type(value["spec_version"]) is not int
        or value["spec_version"] != MODEL_SPEC_VERSION
    ):
        raise ValidationError("Portable ModelSpec version is unsupported")
    for key in ("provider", "model_id", "display_name", "model_type", "source"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            raise ValidationError(
                "Portable Model identity and source must be nonempty strings"
            )
    if (
        "default_model_strategy" in value
        and value["default_model_strategy"] is not None
        and not isinstance(value["default_model_strategy"], str)
    ):
        raise ValidationError("Portable Model strategy must be a string")
    interaction = value.get("interaction")
    if interaction is not None:
        fields = ModelInteractionSpec(mode="isolated").as_dict()
        if not isinstance(interaction, dict) or interaction.keys() - fields.keys():
            raise ValidationError(
                "Portable Model interaction contains unsupported fields"
            )
        for key, item in interaction.items():
            if key == "mode":
                if not isinstance(item, str) or not item.strip():
                    raise ValidationError("Portable Model interaction mode is invalid")
            elif type(item) is not bool:
                raise ValidationError(
                    "Portable Model interaction flags must be boolean"
                )
    limits = value.get("limits")
    if limits is not None:
        if (
            not isinstance(limits, dict)
            or limits.keys() - ModelLimits().as_dict().keys()
        ):
            raise ValidationError("Portable Model limits contain unsupported fields")
        if any(
            item is not None and (type(item) is not int or item <= 0)
            for item in limits.values()
        ):
            raise ValidationError("Portable Model limits must be positive integers")
    capabilities = value.get("capabilities")
    if capabilities is not None:
        if not isinstance(capabilities, dict):
            raise ValidationError("Portable Model capabilities must be an object")
        for capability in capabilities.values():
            if type(capability) is bool:
                continue  # Native legacy capability shorthand remains explicit.
            if (
                not isinstance(capability, dict)
                or capability.keys() - ModelCapability(supported=False).as_dict().keys()
            ):
                raise ValidationError(
                    "Portable Model capability contains unsupported fields"
                )
            if "supported" in capability and type(capability["supported"]) is not bool:
                raise ValidationError(
                    "Portable Model capability support must be boolean"
                )
            if "config" in capability and not isinstance(capability["config"], dict):
                raise ValidationError(
                    "Portable Model capability config must be an object"
                )
    for key in ("metadata", "pricing"):
        if key in value and not isinstance(value[key], dict):
            raise ValidationError("Portable Model metadata and pricing must be objects")
    for key in ("operations", "input_modalities", "output_modalities"):
        if key in value and (
            not isinstance(value[key], list)
            or any(not isinstance(item, str) or not item.strip() for item in value[key])
        ):
            raise ValidationError(
                "Portable Model operation and modality lists must contain strings"
            )
