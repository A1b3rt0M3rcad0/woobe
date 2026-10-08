"""Versioned configuration contracts owned by Strategy registrations."""

from copy import deepcopy

from jsonschema import Draft202012Validator
from referencing import Registry

from shared.contracts.errors import ValidationError


def empty_strategy_config_schema():
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }


def check_strategy_config_schema(schema, version):
    if not isinstance(version, str) or not version or len(version) > 64:
        raise ValueError(
            "Strategy configuration schema version must be a bounded string"
        )
    if not isinstance(schema, dict):
        raise ValueError("Strategy configuration schema must be an object")
    Draft202012Validator.check_schema(schema)


def _no_external_resource(_uri):
    raise ValueError("Strategy configuration schema references must be local")


def validate_strategy_configuration(descriptor, value, *, schema_version):
    if schema_version != descriptor.config_schema_version:
        raise ValidationError("Unsupported Strategy configuration schema version")
    if not isinstance(value, dict):
        raise ValidationError("Strategy configuration must be an object")
    try:
        validator = Draft202012Validator(
            descriptor.config_schema, registry=Registry(retrieve=_no_external_resource)
        )
        invalid = next(validator.iter_errors(value), None)
    except Exception as exc:
        raise ValidationError(
            "Strategy configuration schema cannot be resolved"
        ) from exc
    if invalid is not None:
        raise ValidationError(
            "Strategy configuration does not conform to its registered schema"
        )
    return deepcopy(value)
