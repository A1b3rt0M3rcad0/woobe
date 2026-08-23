from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_TYPE_ALIASES = {
    "str": "string",
    "string": "string",
    "text": "string",
    "int": "integer",
    "integer": "integer",
    "bool": "boolean",
    "boolean": "boolean",
    "float": "number",
    "double": "number",
    "decimal": "number",
    "number": "number",
    "object": "object",
    "dict": "object",
    "array": "array",
    "list": "array",
}

_DECLARATION_TYPES = set(_TYPE_ALIASES)


@dataclass(frozen=True)
class OutputContractValidationError:
    path: str
    expected: str
    received: str
    message: str


def canonical_contract_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _TYPE_ALIASES.get(value.strip().lower())


def _received_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def normalize_contract_for_prompt(schema: Any) -> Any:
    """Return a model-facing contract with aliases made explicit.

    The playground uses a compact DSL where {"confidence": "float"}
    means the runtime output must contain a JSON number. This function keeps
    that compact shape while canonicalizing known aliases so the model is not
    encouraged to emit literal strings such as "number" or "float".
    """
    if isinstance(schema, str):
        return canonical_contract_type(schema) or schema
    if isinstance(schema, list):
        return [normalize_contract_for_prompt(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    normalized: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            normalized[key] = canonical_contract_type(value) or value
        elif key in {"properties", "items"}:
            normalized[key] = normalize_contract_for_prompt(value)
        else:
            normalized[key] = normalize_contract_for_prompt(value)
    return normalized


def _spec_type(spec: Any) -> str | None:
    if isinstance(spec, str):
        return canonical_contract_type(spec)
    if isinstance(spec, dict):
        raw_type = spec.get("type")
        if isinstance(raw_type, str):
            return canonical_contract_type(raw_type)
        if "properties" in spec:
            return "object"
    if isinstance(spec, list):
        return "array"
    return None


def _append_error(
    errors: list[OutputContractValidationError],
    *,
    path: str,
    expected: str,
    actual: Any,
) -> None:
    received = _received_type(actual)
    errors.append(
        OutputContractValidationError(
            path=path,
            expected=expected,
            received=received,
            message=f"{path} expected {expected}, received {received}",
        )
    )


def _validate_spec(
    value: Any,
    spec: Any,
    path: str,
    errors: list[OutputContractValidationError],
) -> None:
    expected = _spec_type(spec)
    if expected and not _matches_type(value, expected):
        _append_error(errors, path=path, expected=expected, actual=value)
        return

    if isinstance(spec, dict):
        properties = spec.get("properties")
        if properties is None and "type" not in spec:
            properties = spec

        if isinstance(properties, dict):
            if not isinstance(value, dict):
                return
            required = spec.get("required")
            required_fields = (
                [item for item in required if isinstance(item, str)]
                if isinstance(required, list)
                else list(properties.keys())
            )
            for field in required_fields:
                if field not in value:
                    errors.append(
                        OutputContractValidationError(
                            path=f"{path}.{field}" if path != "$" else f"$.{field}",
                            expected="present",
                            received="missing",
                            message=f"{path}.{field} is required",
                        )
                    )
            for field, field_spec in properties.items():
                if field in value:
                    field_path = f"{path}.{field}" if path != "$" else f"$.{field}"
                    _validate_spec(value[field], field_spec, field_path, errors)
            if spec.get("additionalProperties") is False:
                for field in value.keys() - properties.keys():
                    field_path = f"{path}.{field}" if path != "$" else f"$.{field}"
                    errors.append(
                        OutputContractValidationError(
                            path=field_path,
                            expected="no additional property",
                            received="present",
                            message=f"{field_path} is not allowed by the output contract",
                        )
                    )
            return

        if expected == "array" and isinstance(value, list):
            item_spec = spec.get("items")
            if item_spec is not None:
                for index, item in enumerate(value):
                    _validate_spec(item, item_spec, f"{path}[{index}]", errors)
            return

    if isinstance(spec, list) and isinstance(value, list) and spec:
        for index, item in enumerate(value):
            _validate_spec(item, spec[0], f"{path}[{index}]", errors)


def validate_output_against_contract(
    parsed_output: Any,
    schema: Any,
) -> list[OutputContractValidationError]:
    if not schema:
        return []
    errors: list[OutputContractValidationError] = []
    _validate_spec(parsed_output, schema, "$", errors)
    return errors


def format_contract_errors(errors: list[OutputContractValidationError]) -> str:
    return "; ".join(error.message for error in errors)
