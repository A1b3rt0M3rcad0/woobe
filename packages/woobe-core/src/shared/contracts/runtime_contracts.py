from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


_SCHEMA_ANNOTATIONS = {"$id", "$schema", "default", "description", "examples", "title"}
_SCHEMA_KEYS = {
    "additionalProperties", "allOf", "anyOf", "const", "definitions", "description",
    "enum", "format", "items", "maxItems", "maxLength", "maximum", "minItems",
    "minLength", "minimum", "oneOf", "pattern", "properties", "required", "schema",
    "title", "type",
}
_SIMPLE_TYPES = {
    "str": "string", "string": "string", "text": "string",
    "number": "number", "float": "number", "double": "number",
    "int": "integer", "integer": "integer",
    "bool": "boolean", "boolean": "boolean",
    "object": "object", "dict": "object",
    "array": "array", "list": "array",
    "null": "null", "none": "null",
}


@dataclass(frozen=True, slots=True)
class RuntimeContractSnapshot:
    release_id: str
    release_version: str
    output_contract: dict[str, Any] | None
    external_context: dict[str, Any] | None


def _parse_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return value


def _looks_like_schema_wrapper(value: Mapping[str, Any]) -> bool:
    return set(value).issubset(
        {"schema", "json_schema", "name", "strict", "type", "description"}
    )


def _looks_like_json_schema(value: Mapping[str, Any]) -> bool:
    keys = set(value)
    if not keys:
        return False
    if keys & {
        "properties", "definitions", "oneOf", "anyOf", "allOf", "enum", "const",
        "items", "required", "additionalProperties",
    }:
        return True
    return keys.issubset(_SCHEMA_KEYS) and "type" in keys


def _contract_value_to_schema(value: Any) -> dict[str, Any]:
    value = _parse_json(value)
    if isinstance(value, str):
        return {"type": _SIMPLE_TYPES.get(value.strip().lower(), "string")}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if value is None:
        return {"type": "null"}
    if isinstance(value, list):
        if len(value) == 1:
            return {"type": "array", "items": _contract_value_to_schema(value[0])}
        return {"type": "array"}
    if not isinstance(value, Mapping):
        return {}

    if (
        isinstance(value.get("schema"), Mapping)
        and "properties" not in value
        and _looks_like_schema_wrapper(value)
    ):
        return _contract_value_to_schema(value["schema"])

    json_schema = value.get("json_schema")
    if isinstance(json_schema, Mapping) and isinstance(json_schema.get("schema"), Mapping):
        return _contract_value_to_schema(json_schema["schema"])

    if _looks_like_json_schema(value):
        normalized = deepcopy(dict(value))
        properties = normalized.get("properties")
        if isinstance(properties, Mapping):
            normalized["properties"] = {
                str(name): _contract_value_to_schema(child)
                for name, child in properties.items()
            }
        if "items" in normalized:
            normalized["items"] = _contract_value_to_schema(normalized["items"])
        for keyword in ("oneOf", "anyOf", "allOf"):
            options = normalized.get(keyword)
            if isinstance(options, list):
                normalized[keyword] = [
                    _contract_value_to_schema(option) for option in options
                ]
        return normalized

    properties = {
        str(name): _contract_value_to_schema(child)
        for name, child in value.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
    }


def _canonicalize(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, Mapping):
        name_map = key in {"properties", "definitions", "$defs", "patternProperties"}
        return {
            str(child_key): _canonicalize(child_value, key=str(child_key))
            for child_key, child_value in sorted(
                value.items(), key=lambda item: str(item[0])
            )
            if name_map or str(child_key) not in _SCHEMA_ANNOTATIONS
        }
    if isinstance(value, list):
        items = [_canonicalize(item) for item in value]
        if key in {"required", "type"}:
            return sorted(items, key=str)
        if key in {"enum", "oneOf", "anyOf", "allOf"}:
            return sorted(
                items,
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            )
        return items
    return value


def normalize_contract_schema(value: Any) -> dict[str, Any] | None:
    value = _parse_json(value)
    if not isinstance(value, Mapping):
        return None
    return _canonicalize(_contract_value_to_schema(value))


def external_context_contract_schema(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None

    legacy_fields = value.get("fields")
    if (
        set(value).issubset({"fields", "additionalProperties"})
        and isinstance(legacy_fields, Mapping)
    ):
        raw_fields: Mapping[str, Any] = legacy_fields
    else:
        raw_fields = value

    properties: dict[str, Any] = {}
    required: list[str] = []
    for raw_name, raw_field in raw_fields.items():
        if not isinstance(raw_field, Mapping):
            continue
        name = str(raw_name)
        properties[name] = _contract_value_to_schema(raw_field.get("schema", {}))
        if raw_field.get("required") is True:
            required.append(name)

    return normalize_contract_schema(
        {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
    )


def effective_external_context_contract_schema(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        return None

    raw_fields = value.get("fields")
    fields = raw_fields if isinstance(raw_fields, Mapping) else value
    properties: dict[str, Any] = {}
    for raw_name, raw_field in fields.items():
        if not isinstance(raw_field, Mapping):
            continue
        properties[str(raw_name)] = _contract_value_to_schema(
            raw_field.get("schema", {})
        )

    return normalize_contract_schema(
        {
            "type": "object",
            "properties": properties,
            "required": [],
            "additionalProperties": False,
        }
    )


def schema_hash(schema: dict[str, Any] | None) -> str:
    payload = json.dumps(
        schema,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _issue(
    code: str,
    path: str,
    *,
    expected: Any = None,
    received: Any = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"code": code, "field": path or "$"}
    if expected is not None:
        result["expected"] = expected
    if received is not None:
        result["received"] = received
    return result


def _schema_issues(
    expected: Mapping[str, Any],
    received: Mapping[str, Any],
    *,
    path: str = "",
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    expected_type = expected.get("type")
    received_type = received.get("type")
    if expected_type != received_type:
        issues.append(
            _issue(
                "FIELD_TYPE_MISMATCH",
                path,
                expected=expected_type,
                received=received_type,
            )
        )
        return issues

    expected_enum = expected.get("enum")
    received_enum = received.get("enum")
    if expected_enum != received_enum:
        issues.append(
            _issue(
                "ENUM_MISMATCH",
                path,
                expected=expected_enum,
                received=received_enum,
            )
        )

    expected_additional = expected.get("additionalProperties", True)
    received_additional = received.get("additionalProperties", True)
    if expected_additional != received_additional:
        issues.append(
            _issue(
                "ADDITIONAL_PROPERTIES_MISMATCH",
                path,
                expected=expected_additional,
                received=received_additional,
            )
        )

    expected_required = set(expected.get("required") or [])
    received_required = set(received.get("required") or [])
    for name in sorted(expected_required - received_required):
        issues.append(_issue("REQUIRED_FIELD_MISSING", f"{path}.{name}".strip(".")))
    for name in sorted(received_required - expected_required):
        issues.append(_issue("UNEXPECTED_REQUIRED_FIELD", f"{path}.{name}".strip(".")))

    expected_properties = expected.get("properties")
    received_properties = received.get("properties")
    if isinstance(expected_properties, Mapping) or isinstance(received_properties, Mapping):
        expected_properties = (
            expected_properties if isinstance(expected_properties, Mapping) else {}
        )
        received_properties = (
            received_properties if isinstance(received_properties, Mapping) else {}
        )
        expected_names = set(expected_properties)
        received_names = set(received_properties)
        for name in sorted(expected_names - received_names):
            issues.append(_issue("FIELD_MISSING", f"{path}.{name}".strip(".")))
        for name in sorted(received_names - expected_names):
            issues.append(_issue("FIELD_EXTRA", f"{path}.{name}".strip(".")))
        for name in sorted(expected_names & received_names):
            left = expected_properties[name]
            right = received_properties[name]
            if isinstance(left, Mapping) and isinstance(right, Mapping):
                issues.extend(
                    _schema_issues(
                        left,
                        right,
                        path=f"{path}.{name}".strip("."),
                    )
                )
            elif left != right:
                issues.append(
                    _issue(
                        "SCHEMA_MISMATCH",
                        f"{path}.{name}".strip("."),
                        expected=left,
                        received=right,
                    )
                )

    expected_items = expected.get("items")
    received_items = received.get("items")
    if isinstance(expected_items, Mapping) and isinstance(received_items, Mapping):
        issues.extend(_schema_issues(expected_items, received_items, path=f"{path}[]"))
    elif expected_items != received_items:
        issues.append(
            _issue(
                "ARRAY_ITEMS_MISMATCH",
                f"{path}[]",
                expected=expected_items,
                received=received_items,
            )
        )

    structural_keys = set(expected) | set(received)
    structural_keys -= {
        "type", "enum", "additionalProperties", "required", "properties", "items",
    }
    for key in sorted(structural_keys):
        if expected.get(key) != received.get(key):
            issues.append(
                _issue(
                    "SCHEMA_MISMATCH",
                    f"{path}.{key}".strip("."),
                    expected=expected.get(key),
                    received=received.get(key),
                )
            )
    return issues


def compare_contract_schema(expected: Any, received: Any) -> dict[str, Any]:
    expected_schema = normalize_contract_schema(expected) if expected is not None else None
    received_schema = normalize_contract_schema(received) if received is not None else None

    if expected_schema is None or received_schema is None:
        valid = expected_schema is None and received_schema is None
        issues = (
            []
            if valid
            else [
                {
                    "code": "CONTRACT_PRESENCE_MISMATCH",
                    "field": "$",
                    "expected": "contract" if expected_schema is not None else None,
                    "received": "contract" if received_schema is not None else None,
                }
            ]
        )
    else:
        issues = _schema_issues(expected_schema, received_schema)
        valid = not issues and expected_schema == received_schema
        if not valid and not issues:
            issues = [{"code": "SCHEMA_MISMATCH", "field": "$"}]

    return {
        "valid": valid,
        "expected": expected_schema,
        "received": received_schema,
        "expected_hash": schema_hash(expected_schema),
        "received_hash": schema_hash(received_schema),
        "issues": issues,
    }


__all__ = [
    "RuntimeContractSnapshot",
    "compare_contract_schema",
    "effective_external_context_contract_schema",
    "external_context_contract_schema",
    "normalize_contract_schema",
    "schema_hash",
]
