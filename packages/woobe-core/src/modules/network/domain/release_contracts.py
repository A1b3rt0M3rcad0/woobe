from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_versioning import ReleaseChangeKind


_AGENT_SNAPSHOT_FIELDS = (
    "prompt_version_id",
    "contract_version_id",
    "knowledge_version_id",
    "model_config_version_id",
    "provider_model_id",
    "fallback_provider_model_id",
    "name",
    "description",
    "behavior_spec",
    "system_prompt",
    "response_format",
    "output_schema",
    "external_context_contract",
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
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def agent_snapshot_payload(release: Any) -> dict[str, Any]:
    return {
        field: _normalize(getattr(release, field, None))
        for field in _AGENT_SNAPSHOT_FIELDS
        if field != "behavior_spec" or getattr(release, field, None) is not None
    }


def agent_snapshot_hash(release: Any) -> str:
    return canonical_hash(agent_snapshot_payload(release))


def output_contract_snapshot(release: Any) -> dict[str, Any] | None:
    response_format = _normalize(getattr(release, "response_format", None))
    output_schema = _normalize(getattr(release, "output_schema", None))
    if isinstance(response_format, dict):
        enabled = bool(response_format.get("enabled"))
        output_type = response_format.get("type")
        schema = response_format.get("schema")
        if not isinstance(schema, dict):
            json_schema = response_format.get("json_schema")
            schema = json_schema.get("schema") if isinstance(json_schema, dict) else None
        if enabled and output_type == "json":
            return {
                "enabled": True,
                "type": "json",
                "strict": bool(response_format.get("strict", False)),
                "schema": deepcopy(schema if isinstance(schema, dict) else output_schema or {}),
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
    previous = _contract_release(previous_contract)
    candidate = _contract_release(candidate_contract)
    return classify_release_change(previous, candidate)


def runtime_settings_hash(definition: Any) -> str:
    settings = getattr(definition, "settings", None)
    if settings is not None and hasattr(settings, "to_dict"):
        settings = settings.to_dict()
    if settings is None:
        settings = {
            "session_mode": getattr(definition, "session_mode", None),
            "max_depth": getattr(getattr(definition, "limits", None), "max_depth", None),
            "max_invocations": getattr(getattr(definition, "limits", None), "max_invocations", None),
            "timeout_seconds": getattr(getattr(definition, "limits", None), "timeout_seconds", None),
        }
    return canonical_hash(settings)


def _contract_release(contract: dict[str, Any] | None) -> AgentRelease:
    release = AgentRelease()
    release.response_format = deepcopy(contract) if contract else None
    release.output_schema = (
        deepcopy(contract.get("schema"))
        if isinstance(contract, dict) and isinstance(contract.get("schema"), dict)
        else None
    )
    return release


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _normalize(child) for key, child in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        return [_normalize(child) for child in value]
    if hasattr(value, "value"):
        return _normalize(value.value)
    return str(value)
