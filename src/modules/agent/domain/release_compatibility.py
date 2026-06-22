from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_versioning import ReleaseChangeKind


def classify_release_change(previous: AgentRelease | None, candidate: AgentRelease) -> ReleaseChangeKind:
    if previous is None:
        return ReleaseChangeKind.CHANGE

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

    return ReleaseChangeKind.CHANGE


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
    if response_format.get("enabled") and (response_format.get("schema") or response_format.get("json_schema")):
        return "json"
    return "text"


def _strict_mode(response_format: dict[str, Any]) -> bool:
    return bool(response_format.get("strict", False))


def _effective_output_schema(release: AgentRelease, response_format: dict[str, Any]) -> dict[str, Any] | None:
    for candidate in (
        release.output_schema,
        response_format.get("schema"),
        (response_format.get("json_schema") or {}).get("schema") if isinstance(response_format.get("json_schema"), dict) else None,
    ):
        normalized = _normalize_schema(candidate)
        if normalized is not None:
            return normalized
    return None


def _normalize_schema(value: Any) -> dict[str, Any] | None:
    value = _parse_json_if_needed(value)
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("schema"), dict) and "properties" not in value:
        value = value["schema"]
    if isinstance(value.get("json_schema"), dict) and isinstance(value["json_schema"].get("schema"), dict):
        value = value["json_schema"]["schema"]
    return deepcopy(value)


def _schema_breaks_compatibility(previous: dict[str, Any] | None, candidate: dict[str, Any] | None) -> bool:
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

    if previous.get("additionalProperties", True) is True and candidate.get("additionalProperties", True) is False:
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


def _schema_adds_non_breaking_feature(previous: dict[str, Any] | None, candidate: dict[str, Any] | None) -> bool:
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
