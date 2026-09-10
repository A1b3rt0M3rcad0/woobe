from __future__ import annotations

from hashlib import sha256
import json
from typing import Any
from uuid import UUID


SNAPSHOT_FIELDS = (
    "project_id",
    "agent_id",
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
    "risk_score",
)

_EMPTY_OBJECT_FIELDS = {"response_format", "runtime_config"}


def _canonical_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return value


def canonical_release_snapshot(release: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for field_name in SNAPSHOT_FIELDS:
        value = getattr(release, field_name, None)
        if field_name == "behavior_spec" and value is None:
            continue  # Preserve legacy snapshot hashes.
        if field_name in _EMPTY_OBJECT_FIELDS and value is None:
            value = {}
        if field_name == "collection_ids" and value:
            value = sorted(value, key=str)
        snapshot[field_name] = _canonical_value(value)
    return snapshot


def release_snapshot_hash(release: Any) -> str:
    payload = json.dumps(
        canonical_release_snapshot(release),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def release_snapshots_equal(left: Any, right: Any) -> bool:
    return release_snapshot_hash(left) == release_snapshot_hash(right)
