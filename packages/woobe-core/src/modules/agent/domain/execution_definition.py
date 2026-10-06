"""Versioned identity for executable Agent definitions, independent of lifecycle.

Version 1 remains in release_snapshot for historical receipts. Version 2 covers
every executable field and is domain separated; stored Release hashes are never
rewritten when a new comparison contract is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any
from uuid import UUID


AGENT_EXECUTION_FIELDS = (
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
    "model_spec_snapshot",
    "model_spec_hash",
    "fallback_model_spec_snapshot",
    "fallback_model_spec_hash",
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
AGENT_SNAPSHOT_FIELDS = ("project_id", "agent_id", *AGENT_EXECUTION_FIELDS)
SNAPSHOT_SCHEMA_VERSION = "2"


def canonical_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(key): canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if hasattr(value, "value"):
        return canonical_value(value.value)
    return value


def canonicalize_agent_execution_definition(source: Any) -> dict[str, Any]:
    result = {}
    for field in AGENT_EXECUTION_FIELDS:
        value = (
            source.get(field)
            if isinstance(source, dict)
            else getattr(source, field, None)
        )
        if field in {"response_format", "runtime_config"} and value is None:
            value = {}
        if field == "collection_ids" and value:
            value = sorted(value, key=str)
        result[field] = canonical_value(value)
    return result


@dataclass(frozen=True, slots=True)
class AgentExecutionDefinition:
    fields: dict[str, Any]

    @classmethod
    def from_source(cls, source: Any) -> AgentExecutionDefinition:
        return cls(canonicalize_agent_execution_definition(source))


@dataclass(frozen=True, slots=True)
class AgentExecutionSnapshot:
    definition: AgentExecutionDefinition
    project_id: str | None
    agent_id: str | None
    schema_version: str = SNAPSHOT_SCHEMA_VERSION

    @classmethod
    def from_source(cls, source: Any) -> AgentExecutionSnapshot:
        def identity(field: str) -> str | None:
            value = (
                source.get(field)
                if isinstance(source, dict)
                else getattr(source, field, None)
            )
            return str(value) if value is not None else None

        return cls(
            AgentExecutionDefinition.from_source(source),
            identity("project_id"),
            identity("agent_id"),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "agent_id": self.agent_id,
            "definition": self.definition.fields,
        }


def hash_agent_execution_snapshot(source: Any) -> str:
    snapshot = (
        source
        if isinstance(source, AgentExecutionSnapshot)
        else AgentExecutionSnapshot.from_source(source)
    )
    encoded = json.dumps(
        snapshot.as_dict(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(b"woobe-agent-execution-snapshot@2\n" + encoded).hexdigest()
