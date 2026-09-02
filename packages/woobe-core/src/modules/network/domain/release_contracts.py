from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from modules.network.domain.release_versioning import ReleaseChangeKind


_AGENT_SNAPSHOT_FIELDS = (
    "prompt_version_id",
    "contract_version_id",
    "knowledge_version_id",
    "model_config_version_id",
    "provider_model_id",
    "fallback_provider_model_id",
    "name",
    "description",
    "system_prompt",
    "response_format",
    "output_schema",
    "provider",
    "model",
    "provider_credential_id",
    "fallback_provider",
    "fallback_model",
    "fallback_credential_id",
    "base_url",
    "temperature",
    "max_output_tokens",
    "session_mode",
    "agent_status",
    "collection_ids",
    "runtime_config",
)


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def agent_snapshot_payload(release: Any) -> dict[str, Any]:
    return {
        field: _normalize(_value(release, field))
        for field in _AGENT_SNAPSHOT_FIELDS
    }


def agent_snapshot_hash(release: Any) -> str:
    return canonical_hash(agent_snapshot_payload(release))


def output_contract_snapshot(release: Any) -> dict[str, Any] | None:
    response_format = _normalize(_value(release, "response_format"))
    output_schema = _normalize(_value(release, "output_schema"))
    if isinstance(response_format, dict):
        raw_type = response_format.get("type")
        enabled = bool(response_format.get("enabled"))
        schema = response_format.get("schema")
        if not isinstance(schema, dict):
            json_schema = response_format.get("json_schema")
            schema = (
                json_schema.get("schema")
                if isinstance(json_schema, dict)
                else None
            )
        if enabled and raw_type in {"json", "json_object", "json_schema"}:
            return {
                "enabled": True,
                "type": "json",
                "strict": bool(response_format.get("strict", False)),
                "schema": deepcopy(
                    schema if isinstance(schema, dict) else output_schema or {}
                ),
            }
    if isinstance(output_schema, dict) and output_schema:
        return {
            "enabled": True,
            "type": "json",
            "strict": True,
            "schema": deepcopy(output_schema),
        }
    return None


def output_contract_hash(release: Any) -> str:
    return canonical_hash(output_contract_snapshot(release))


def classify_contract_change(
    previous_contract: dict[str, Any] | None,
    candidate_contract: dict[str, Any] | None,
) -> ReleaseChangeKind:
    if previous_contract is None:
        return ReleaseChangeKind.CHANGE
    if candidate_contract is None:
        return ReleaseChangeKind.COMPATIBILITY
    if previous_contract == candidate_contract:
        return ReleaseChangeKind.CHANGE

    previous_type = str(previous_contract.get("type") or "text")
    candidate_type = str(candidate_contract.get("type") or "text")
    if previous_type != candidate_type:
        return ReleaseChangeKind.COMPATIBILITY
    if bool(previous_contract.get("strict")) != bool(candidate_contract.get("strict")):
        return ReleaseChangeKind.COMPATIBILITY

    previous_schema = previous_contract.get("schema")
    candidate_schema = candidate_contract.get("schema")
    if not isinstance(previous_schema, dict):
        previous_schema = {}
    if not isinstance(candidate_schema, dict):
        candidate_schema = {}

    if _schema_breaks_compatibility(previous_schema, candidate_schema):
        return ReleaseChangeKind.COMPATIBILITY
    if _schema_adds_non_breaking_feature(previous_schema, candidate_schema):
        return ReleaseChangeKind.FEATURE
    return ReleaseChangeKind.CHANGE


def runtime_settings_hash(definition: Any) -> str:
    settings = getattr(definition, "settings", None)
    if settings is not None and hasattr(settings, "to_dict"):
        settings = settings.to_dict()
    if settings is None:
        limits = getattr(definition, "limits", None)
        settings = {
            "session_mode": getattr(definition, "session_mode", None),
            "max_depth": getattr(limits, "max_depth", None),
            "max_invocations": getattr(limits, "max_invocations", None),
            "timeout_seconds": getattr(limits, "timeout_seconds", None),
        }
    return canonical_hash(settings)


def _schema_breaks_compatibility(
    previous: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    previous_type = previous.get("type")
    candidate_type = candidate.get("type")
    if previous_type and candidate_type and previous_type != candidate_type:
        return True

    previous_enum = previous.get("enum")
    candidate_enum = candidate.get("enum")
    if isinstance(previous_enum, list) and isinstance(candidate_enum, list):
        if not set(previous_enum).issubset(set(candidate_enum)):
            return True

    previous_props = previous.get("properties")
    candidate_props = candidate.get("properties")
    if isinstance(previous_props, dict):
        if not isinstance(candidate_props, dict):
            return True
        for name, previous_child in previous_props.items():
            candidate_child = candidate_props.get(name)
            if candidate_child is None:
                return True
            if isinstance(previous_child, dict) and isinstance(candidate_child, dict):
                if _schema_breaks_compatibility(previous_child, candidate_child):
                    return True

    previous_required = set(previous.get("required") or [])
    candidate_required = set(candidate.get("required") or [])
    if not previous_required.issubset(candidate_required):
        return True
    if candidate_required - set((previous_props or {}).keys()):
        return True

    if (
        previous.get("additionalProperties", True) is True
        and candidate.get("additionalProperties", True) is False
    ):
        return True

    previous_items = previous.get("items")
    candidate_items = candidate.get("items")
    if isinstance(previous_items, dict):
        if not isinstance(candidate_items, dict):
            return True
        if _schema_breaks_compatibility(previous_items, candidate_items):
            return True
    return False


def _schema_adds_non_breaking_feature(
    previous: dict[str, Any],
    candidate: dict[str, Any],
) -> bool:
    previous_props = previous.get("properties")
    candidate_props = candidate.get("properties")
    if isinstance(previous_props, dict) and isinstance(candidate_props, dict):
        if set(candidate_props) - set(previous_props):
            return True
        for name, previous_child in previous_props.items():
            candidate_child = candidate_props.get(name)
            if isinstance(previous_child, dict) and isinstance(candidate_child, dict):
                if _schema_adds_non_breaking_feature(previous_child, candidate_child):
                    return True

    previous_enum = previous.get("enum")
    candidate_enum = candidate.get("enum")
    if isinstance(previous_enum, list) and isinstance(candidate_enum, list):
        if set(candidate_enum) - set(previous_enum):
            return True

    previous_items = previous.get("items")
    candidate_items = candidate.get("items")
    if isinstance(previous_items, dict) and isinstance(candidate_items, dict):
        return _schema_adds_non_breaking_feature(previous_items, candidate_items)
    return False


def _value(source: Any, field: str) -> Any:
    if isinstance(source, dict):
        return source.get(field)
    return getattr(source, field, None)


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _normalize(child)
            for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        return [_normalize(child) for child in value]
    if hasattr(value, "value"):
        return _normalize(value.value)
    return str(value)
