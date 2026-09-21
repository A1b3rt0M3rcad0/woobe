from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.external_context_contract import classify_external_context_change
from modules.agent.domain.release_versioning import ReleaseChangeKind


_SCHEMA_KEYS = {
    "additionalProperties",
    "allOf",
    "anyOf",
    "const",
    "definitions",
    "description",
    "enum",
    "format",
    "items",
    "maxItems",
    "maxLength",
    "maximum",
    "minItems",
    "minLength",
    "minimum",
    "oneOf",
    "pattern",
    "properties",
    "required",
    "schema",
    "title",
    "type",
}

_SIMPLE_TYPES = {
    "str": "string",
    "string": "string",
    "text": "string",
    "number": "number",
    "float": "number",
    "double": "number",
    "int": "integer",
    "integer": "integer",
    "bool": "boolean",
    "boolean": "boolean",
    "object": "object",
    "dict": "object",
    "array": "array",
    "list": "array",
    "null": "null",
    "none": "null",
}


def classify_release_change(
    previous: AgentRelease | None,
    candidate: AgentRelease,
) -> ReleaseChangeKind:
    if previous is None:
        return ReleaseChangeKind.CHANGE

    if previous.session_mode != candidate.session_mode:
        return ReleaseChangeKind.COMPATIBILITY

    external_context_kind = classify_external_context_change(
        previous.external_context_contract,
        candidate.external_context_contract,
    )
    if external_context_kind is ReleaseChangeKind.COMPATIBILITY:
        return ReleaseChangeKind.COMPATIBILITY

    simple_contract_kind = _simple_contract_change_kind(
        previous.output_schema,
        candidate.output_schema,
    )
    if simple_contract_kind is not None:
        return simple_contract_kind

    previous_format = _normalize_response_format(previous)
    candidate_format = _normalize_response_format(candidate)

    if _response_type(previous_format) != _response_type(candidate_format):
        return ReleaseChangeKind.COMPATIBILITY
    if _strict_mode(previous_format) != _strict_mode(candidate_format):
        return ReleaseChangeKind.COMPATIBILITY

    previous_schema = _effective_output_schema(previous, previous_format)
    candidate_schema = _effective_output_schema(candidate, candidate_format)

    if _schema_breaks_compatibility(previous_schema, candidate_schema):
        return ReleaseChangeKind.COMPATIBILITY
    if _schema_adds_non_breaking_feature(previous_schema, candidate_schema):
        return ReleaseChangeKind.FEATURE

    if external_context_kind is ReleaseChangeKind.FEATURE:
        return ReleaseChangeKind.FEATURE
    return ReleaseChangeKind.CHANGE


_OUTPUT_SCHEMA_ANNOTATIONS = {
    "$id",
    "$schema",
    "default",
    "description",
    "examples",
    "title",
}


def _canonicalize_output_schema_node(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(child_key): _canonicalize_output_schema_node(
                child_value,
                key=str(child_key),
            )
            for child_key, child_value in sorted(
                value.items(),
                key=lambda item: str(item[0]),
            )
            if str(child_key) not in _OUTPUT_SCHEMA_ANNOTATIONS
        }
    if isinstance(value, list):
        items = [
            _canonicalize_output_schema_node(item)
            for item in value
        ]
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


def _normalize_public_output_value(value: Any) -> dict[str, Any]:
    value = _parse_json_if_needed(value)
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
            return {
                "type": "array",
                "items": _normalize_public_output_value(value[0]),
            }
        return {"type": "array"}
    if not isinstance(value, dict):
        return {}

    if (
        isinstance(value.get("schema"), dict)
        and "properties" not in value
        and _looks_like_schema_wrapper(value)
    ):
        return _normalize_public_output_value(value["schema"])
    if isinstance(value.get("json_schema"), dict) and isinstance(
        value["json_schema"].get("schema"),
        dict,
    ):
        return _normalize_public_output_value(value["json_schema"]["schema"])
    if _looks_like_json_schema(value):
        return _normalize_json_schema(value)

    properties = {
        str(name): _normalize_public_output_value(child)
        for name, child in value.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties.keys()),
    }


def normalize_output_schema(value: Any) -> dict[str, Any] | None:
    """Normalize compact or JSON Schema output contracts for public boundaries."""
    value = _parse_json_if_needed(value)
    if not isinstance(value, dict):
        return None
    return _canonicalize_output_schema_node(_normalize_public_output_value(value))


def effective_output_schema(release: Any) -> dict[str, Any] | None:
    """Return the effective structured-output schema frozen in a Release."""
    response_format = _normalize_response_format(release)
    for candidate in (
        getattr(release, "output_schema", None),
        response_format.get("schema"),
        (response_format.get("json_schema") or {}).get("schema")
        if isinstance(response_format.get("json_schema"), dict)
        else None,
    ):
        normalized = normalize_output_schema(candidate)
        if normalized is not None:
            return normalized
    return None


def output_schemas_equivalent(left: Any, right: Any) -> bool:
    """Compare output contracts by structural semantics rather than annotations."""
    left_schema = normalize_output_schema(left)
    right_schema = normalize_output_schema(right)
    return left_schema == right_schema


def _simple_contract_change_kind(
    previous: Any,
    candidate: Any,
) -> ReleaseChangeKind | None:
    previous = _parse_json_if_needed(previous)
    candidate = _parse_json_if_needed(candidate)
    if not isinstance(previous, dict) or not isinstance(candidate, dict):
        return None
    if _looks_like_json_schema(previous) or _looks_like_json_schema(candidate):
        return None

    previous_keys = set(previous.keys())
    candidate_keys = set(candidate.keys())
    if not previous_keys.issubset(candidate_keys):
        return ReleaseChangeKind.COMPATIBILITY

    for key in previous_keys:
        if _simple_value_type(previous[key]) != _simple_value_type(candidate[key]):
            return ReleaseChangeKind.COMPATIBILITY

    if candidate_keys - previous_keys:
        return ReleaseChangeKind.FEATURE
    return None


def _simple_value_type(value: Any) -> str:
    if isinstance(value, str):
        return _SIMPLE_TYPES.get(value.strip().lower(), "string")
    return str(_contract_value_to_schema(value).get("type", ""))


def _normalize_response_format(release: AgentRelease) -> dict[str, Any]:
    value = release.response_format or {}
    value = _parse_json_if_needed(value)
    return deepcopy(value) if isinstance(value, dict) else {}


def _parse_json_if_needed(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def _response_type(response_format: dict[str, Any]) -> str:
    raw_type = response_format.get("type")
    if raw_type in ("json", "json_object", "json_schema"):
        return "json"
    if response_format.get("enabled") and (
        response_format.get("schema") or response_format.get("json_schema")
    ):
        return "json"
    return "text"


def _strict_mode(response_format: dict[str, Any]) -> bool:
    return bool(response_format.get("strict", False))


def _effective_output_schema(
    release: AgentRelease,
    response_format: dict[str, Any],
) -> dict[str, Any] | None:
    for candidate in (
        release.output_schema,
        response_format.get("schema"),
        (response_format.get("json_schema") or {}).get("schema")
        if isinstance(response_format.get("json_schema"), dict)
        else None,
    ):
        normalized = _normalize_schema(candidate)
        if normalized is not None:
            return normalized
    return None


def _normalize_schema(value: Any) -> dict[str, Any] | None:
    value = _parse_json_if_needed(value)
    if not isinstance(value, dict):
        return None
    if (
        isinstance(value.get("schema"), dict)
        and "properties" not in value
        and _looks_like_schema_wrapper(value)
    ):
        value = value["schema"]
    if isinstance(value.get("json_schema"), dict) and isinstance(
        value["json_schema"].get("schema"),
        dict,
    ):
        value = value["json_schema"]["schema"]
    if _looks_like_json_schema(value):
        return _normalize_json_schema(value)
    return _simple_contract_to_object_schema(value)


def _looks_like_schema_wrapper(value: dict[str, Any]) -> bool:
    return set(value.keys()).issubset(
        {"schema", "json_schema", "name", "strict", "type", "description"}
    )


def _looks_like_json_schema(value: dict[str, Any]) -> bool:
    keys = set(value.keys())
    if not keys:
        return False
    if keys & {
        "properties",
        "definitions",
        "oneOf",
        "anyOf",
        "allOf",
        "enum",
        "const",
        "items",
        "required",
        "additionalProperties",
    }:
        return True
    return keys.issubset(_SCHEMA_KEYS) and "type" in keys


def _normalize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(schema)
    properties = normalized.get("properties")
    if isinstance(properties, dict):
        normalized["properties"] = {
            str(name): _contract_value_to_schema(child)
            for name, child in properties.items()
        }
    if "items" in normalized:
        normalized["items"] = _contract_value_to_schema(normalized["items"])
    for keyword in ("oneOf", "anyOf", "allOf"):
        options = normalized.get(keyword)
        if isinstance(options, list):
            normalized[keyword] = [_contract_value_to_schema(option) for option in options]
    return normalized


def _simple_contract_to_object_schema(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            str(name): _contract_value_to_schema(child)
            for name, child in contract.items()
        },
    }


def _contract_value_to_schema(value: Any) -> dict[str, Any]:
    value = _parse_json_if_needed(value)
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
    if isinstance(value, dict):
        if _looks_like_json_schema(value):
            return _normalize_json_schema(value)
        return _simple_contract_to_object_schema(value)
    return {}


def _schema_breaks_compatibility(
    previous: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> bool:
    if previous is None and candidate is None:
        return False
    if previous is None:
        return False
    if candidate is None:
        return True
    return _schema_node_breaks(previous, candidate)


def _schema_node_breaks(previous: dict[str, Any], candidate: dict[str, Any]) -> bool:
    previous_type = _schema_type(previous)
    candidate_type = _schema_type(candidate)
    if previous_type and candidate_type and previous_type != candidate_type:
        return True

    if previous_type == "object" or "properties" in previous:
        return _object_schema_breaks(previous, candidate)
    if previous_type == "array" or "items" in previous:
        return _array_schema_breaks(previous, candidate)

    return _enum_breaks(previous, candidate)


def _object_schema_breaks(previous: dict[str, Any], candidate: dict[str, Any]) -> bool:
    previous_props = previous.get("properties") or {}
    candidate_props = candidate.get("properties") or {}
    if not isinstance(previous_props, dict) or not isinstance(candidate_props, dict):
        return False

    for name, previous_child in previous_props.items():
        if name not in candidate_props:
            return True
        if isinstance(previous_child, dict) and isinstance(candidate_props[name], dict):
            if _schema_node_breaks(previous_child, candidate_props[name]):
                return True

    previous_required = set(previous.get("required") or [])
    candidate_required = set(candidate.get("required") or [])
    if not previous_required.issubset(candidate_required):
        return True
    if candidate_required - set(previous_props.keys()):
        return True

    if (
        previous.get("additionalProperties", True) is True
        and candidate.get("additionalProperties", True) is False
    ):
        return True

    return _enum_breaks(previous, candidate)


def _array_schema_breaks(previous: dict[str, Any], candidate: dict[str, Any]) -> bool:
    previous_items = previous.get("items")
    candidate_items = candidate.get("items")
    if isinstance(previous_items, dict) and isinstance(candidate_items, dict):
        return _schema_node_breaks(previous_items, candidate_items)
    if previous_items and not candidate_items:
        return True
    return False


def _enum_breaks(previous: dict[str, Any], candidate: dict[str, Any]) -> bool:
    previous_enum = previous.get("enum")
    candidate_enum = candidate.get("enum")
    if isinstance(previous_enum, list) and isinstance(candidate_enum, list):
        return not set(previous_enum).issubset(set(candidate_enum))
    return False


def _schema_adds_non_breaking_feature(
    previous: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> bool:
    if previous is None and candidate is not None:
        return True
    if previous is None or candidate is None:
        return False
    return _schema_node_adds_feature(previous, candidate)


def _schema_node_adds_feature(previous: dict[str, Any], candidate: dict[str, Any]) -> bool:
    previous_props = previous.get("properties") or {}
    candidate_props = candidate.get("properties") or {}
    if isinstance(previous_props, dict) and isinstance(candidate_props, dict):
        if set(candidate_props.keys()) - set(previous_props.keys()):
            return True
        for name, previous_child in previous_props.items():
            candidate_child = candidate_props.get(name)
            if isinstance(previous_child, dict) and isinstance(candidate_child, dict):
                if _schema_node_adds_feature(previous_child, candidate_child):
                    return True

    previous_enum = previous.get("enum")
    candidate_enum = candidate.get("enum")
    if isinstance(previous_enum, list) and isinstance(candidate_enum, list):
        if set(candidate_enum) - set(previous_enum):
            return True

    previous_items = previous.get("items")
    candidate_items = candidate.get("items")
    if isinstance(previous_items, dict) and isinstance(candidate_items, dict):
        return _schema_node_adds_feature(previous_items, candidate_items)

    return False


def _schema_type(schema: dict[str, Any]) -> str | None:
    raw = schema.get("type")
    if isinstance(raw, list):
        return "|".join(sorted(str(item) for item in raw))
    if raw is None:
        return None
    return str(raw)
