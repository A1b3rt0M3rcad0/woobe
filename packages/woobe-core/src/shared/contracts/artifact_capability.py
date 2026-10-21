"""Versioned, portable Artifact capability contract for Agent definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared.contracts.errors import ValidationError


class ArtifactWorkspaceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    field: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    namespace: str = Field(min_length=1, max_length=255)
    scope: Literal["run", "session"]


class ArtifactReadLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    max_search_results: int = Field(default=20, ge=1, le=200)
    max_read_chars: int = Field(default=8192, ge=1, le=65_536)
    max_total_read_chars: int = Field(default=65_536, ge=1, le=1_048_576)
    max_context_units: int = Field(default=8000, ge=64, le=1_000_000)
    max_writes: int = Field(default=0, ge=0, le=100)


class ArtifactProcessingProfileRef(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    ref: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    revision: int = Field(default=1, ge=1, le=1_000_000)


class ArtifactCapability(BaseModel):
    """Capability is off for legacy definitions and contains no private IDs."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal[1] = 1
    enabled: bool = False
    workspace_binding: ArtifactWorkspaceBinding | None = None
    actions: tuple[Literal["read", "search", "write", "delete", "process", "transfer"], ...] = (
        "read",
        "search",
    )
    limits: ArtifactReadLimits = Field(default_factory=ArtifactReadLimits)
    processing_profile: ArtifactProcessingProfileRef | None = None

    @field_validator("actions", mode="before")
    @classmethod
    def parse_actions(cls, value):
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def validate_capability(self):
        if len(set(self.actions)) != len(self.actions):
            raise ValueError("Artifact capability actions must be unique")
        if not self.enabled:
            if self.workspace_binding is not None or self.processing_profile is not None:
                raise ValueError("Disabled Artifact capability cannot bind a Workspace or profile")
            if self.actions != ("read", "search") or self.limits != ArtifactReadLimits():
                raise ValueError("Disabled Artifact capability cannot carry active policy")
            return self
        if self.workspace_binding is None:
            raise ValueError("Enabled Artifact capability requires a Workspace binding")
        if not self.actions:
            raise ValueError("Enabled Artifact capability requires at least one action")
        if ("write" in self.actions) != (self.limits.max_writes > 0):
            raise ValueError("Artifact write action and max_writes limit must agree")
        if self.processing_profile is not None and "process" not in self.actions:
            raise ValueError("Processing profile requires the process action")
        return self


def canonicalize_artifact_capability(value, external_context_contract) -> dict | None:
    """Validate a definition against its declared External Context field and freeze it."""
    if value is None:
        return None
    try:
        capability = ArtifactCapability.model_validate(value)
        if capability.enabled:
            contract = external_context_contract or {}
            if not isinstance(contract, dict):
                raise ValueError("External Context contract must be an object")
            if set(contract).issubset({"fields", "additionalProperties"}) and isinstance(
                contract.get("fields"), dict
            ):
                fields = contract["fields"]
            else:
                fields = contract
            binding = capability.workspace_binding
            assert binding is not None
            field = fields.get(binding.field)
            if not isinstance(field, dict):
                raise ValueError("Artifact Workspace binding field is not declared in External Context")
            if field.get("scope", "run") != binding.scope:
                raise ValueError("Artifact Workspace binding scope differs from External Context")
            if field.get("schema", {}).get("type") != "string":
                raise ValueError("Artifact Workspace binding must use a string External Context field")
            if not field.get("required") or "default" in field:
                raise ValueError("Artifact Workspace binding must be required and cannot have a default")
            if field.get("model", {}).get("expose", False):
                raise ValueError("Artifact Workspace binding cannot be exposed to the model")
        return capability.model_dump(mode="json")
    except (TypeError, ValueError) as error:
        raise ValidationError(f"Invalid Artifact capability: {error}") from error


def canonicalize_artifact_runtime_config(runtime_config, external_context_contract):
    if runtime_config is None:
        return None
    if not isinstance(runtime_config, dict):
        raise ValidationError("Agent runtime_config must be an object")
    normalized = dict(runtime_config)
    if "artifacts" in normalized:
        normalized["artifacts"] = canonicalize_artifact_capability(
            normalized["artifacts"], external_context_contract
        )
    return normalized


__all__ = [
    "ArtifactCapability",
    "ArtifactProcessingProfileRef",
    "ArtifactReadLimits",
    "ArtifactWorkspaceBinding",
    "canonicalize_artifact_capability",
    "canonicalize_artifact_runtime_config",
]
