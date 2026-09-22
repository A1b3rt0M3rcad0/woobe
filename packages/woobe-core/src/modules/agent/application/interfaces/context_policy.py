from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from modules.agent.domain.context import (
    ContextPriority,
    ContextRetentionMode,
    ContextSourceType,
)


class SessionContextPolicy(BaseModel):
    strategy: Literal["recent"] = "recent"
    max_messages: int = Field(default=20, ge=1, le=200)
    max_units: int | None = Field(default=None, ge=128, le=1_000_000)


class CheckpointContextPolicy(BaseModel):
    max_units: int | None = Field(default=None, ge=128, le=1_000_000)


class MemoryContextPolicy(BaseModel):
    max_units: int | None = Field(default=None, ge=128, le=1_000_000)


class KnowledgeContextPolicy(BaseModel):
    max_units: int | None = Field(default=None, ge=128, le=1_000_000)


class ToolContextPolicy(BaseModel):
    max_result_units: int | None = Field(default=None, ge=64, le=1_000_000)


class ArtifactContextPolicy(BaseModel):
    strategy: Literal["reference_first", "materialize"] = "reference_first"
    max_units: int | None = Field(default=None, ge=64, le=1_000_000)


class DelegationContextPolicy(BaseModel):
    max_units: int | None = Field(default=None, ge=64, le=1_000_000)


class ContextBudgetPolicy(BaseModel):
    max_input_units: int | None = Field(default=None, ge=256, le=4_000_000)
    runtime_reserve_units: int = Field(default=0, ge=0, le=1_000_000)


class ContextRetentionPolicy(BaseModel):
    materialized_content: ContextRetentionMode = ContextRetentionMode.REFERENCES_ONLY

    @model_validator(mode="after")
    def validate_v1_retention(self) -> "ContextRetentionPolicy":
        if self.materialized_content != ContextRetentionMode.REFERENCES_ONLY:
            raise ValueError(
                "Context Policy v1 supports only references_only retention"
            )
        return self


class ContextPressurePolicy(BaseModel):
    moderate_at: float = Field(default=0.40, gt=0, lt=1)
    high_at: float = Field(default=0.75, gt=0, lt=1)
    critical_at: float = Field(default=0.90, gt=0, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> "ContextPressurePolicy":
        if not self.moderate_at < self.high_at < self.critical_at:
            raise ValueError("context pressure thresholds must be strictly increasing")
        return self


class ContextSummaryPolicy(BaseModel):
    strategy: Literal["disabled", "pressure_triggered", "rolling"] = "disabled"
    sources: list[ContextSourceType] = Field(
        default_factory=lambda: [ContextSourceType.SESSION]
    )
    trigger_at: float = Field(default=0.75, gt=0, le=1)
    target_units: int = Field(default=2000, ge=128, le=250_000)
    preserve_recent_messages: int = Field(default=8, ge=0, le=200)
    refresh_after_messages: int = Field(default=12, ge=1, le=500)
    failure_mode: Literal["fallback_to_selection", "fail"] = "fallback_to_selection"

    @model_validator(mode="after")
    def validate_sources(self) -> "ContextSummaryPolicy":
        forbidden = {
            ContextSourceType.SYSTEM,
            ContextSourceType.USER_INPUT,
        }
        if any(source in forbidden for source in self.sources):
            raise ValueError("Context Summary cannot target mandatory SYSTEM/USER_INPUT")
        self.sources = list(dict.fromkeys(self.sources))
        return self


class ContextOrderingPolicy(BaseModel):
    strategy: Literal["preserve_input", "source_priority"] = "preserve_input"


class ContextDeduplicationPolicy(BaseModel):
    strategy: Literal["none", "content_hash"] = "none"
    sources: list[ContextSourceType] = Field(
        default_factory=lambda: [
            ContextSourceType.SESSION,
            ContextSourceType.CHECKPOINT,
            ContextSourceType.MEMORY,
            ContextSourceType.KNOWLEDGE,
            ContextSourceType.TOOL,
            ContextSourceType.ARTIFACT,
            ContextSourceType.RUNTIME,
        ]
    )


def _default_source_priorities() -> dict[ContextSourceType, ContextPriority]:
    return {
        ContextSourceType.SYSTEM: ContextPriority.MANDATORY,
        ContextSourceType.USER_INPUT: ContextPriority.MANDATORY,
        ContextSourceType.SESSION: ContextPriority.HIGH,
        ContextSourceType.CHECKPOINT: ContextPriority.HIGH,
        ContextSourceType.MEMORY: ContextPriority.HIGH,
        ContextSourceType.KNOWLEDGE: ContextPriority.DYNAMIC,
        ContextSourceType.TOOL: ContextPriority.DYNAMIC,
        ContextSourceType.ARTIFACT: ContextPriority.DYNAMIC,
        ContextSourceType.DELEGATION: ContextPriority.HIGH,
        ContextSourceType.RUNTIME: ContextPriority.DYNAMIC,
    }


class SkillContextPolicy(BaseModel):
    catalog_max_units: int = Field(default=2000, ge=128, le=100_000)
    max_units: int = Field(default=8000, ge=256, le=1_000_000)
    search_limit: int = Field(default=8, ge=1, le=50)


class ContextPolicyV1(BaseModel):
    schema_version: Literal[1] = 1
    skills: SkillContextPolicy | None = Field(default=None, exclude_if=lambda value: value is None)
    allowed_sources: list[ContextSourceType] = Field(
        default_factory=lambda: [
            ContextSourceType.SYSTEM,
            ContextSourceType.USER_INPUT,
            ContextSourceType.SESSION,
            ContextSourceType.KNOWLEDGE,
            ContextSourceType.TOOL,
            ContextSourceType.DELEGATION,
            ContextSourceType.RUNTIME,
        ]
    )
    source_priorities: dict[ContextSourceType, ContextPriority] = Field(
        default_factory=_default_source_priorities
    )
    session: SessionContextPolicy = Field(default_factory=SessionContextPolicy)
    checkpoints: CheckpointContextPolicy = Field(default_factory=CheckpointContextPolicy)
    memory: MemoryContextPolicy = Field(default_factory=MemoryContextPolicy)
    knowledge: KnowledgeContextPolicy = Field(default_factory=KnowledgeContextPolicy)
    tools: ToolContextPolicy = Field(default_factory=ToolContextPolicy)
    artifacts: ArtifactContextPolicy = Field(default_factory=ArtifactContextPolicy)
    delegation: DelegationContextPolicy = Field(default_factory=DelegationContextPolicy)
    budget: ContextBudgetPolicy = Field(default_factory=ContextBudgetPolicy)
    retention: ContextRetentionPolicy = Field(default_factory=ContextRetentionPolicy)
    pressure: ContextPressurePolicy = Field(default_factory=ContextPressurePolicy)
    summary: ContextSummaryPolicy = Field(default_factory=ContextSummaryPolicy)
    ordering: ContextOrderingPolicy = Field(default_factory=ContextOrderingPolicy)
    deduplication: ContextDeduplicationPolicy = Field(
        default_factory=ContextDeduplicationPolicy
    )

    @model_validator(mode="after")
    def complete_and_validate_priorities(self) -> "ContextPolicyV1":
        merged = _default_source_priorities()
        merged.update(self.source_priorities)
        if merged[ContextSourceType.SYSTEM] != ContextPriority.MANDATORY:
            raise ValueError("SYSTEM context priority must remain MANDATORY")
        if merged[ContextSourceType.USER_INPUT] != ContextPriority.MANDATORY:
            raise ValueError("USER_INPUT context priority must remain MANDATORY")
        self.source_priorities = merged
        return self


def resolve_context_policy(runtime_config: object) -> ContextPolicyV1:
    runtime = runtime_config if isinstance(runtime_config, dict) else {}
    raw = runtime.get("context")
    return ContextPolicyV1.model_validate(raw if isinstance(raw, dict) else {})


def canonicalize_context_runtime_config(value: object) -> dict:
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    policy = resolve_context_policy(runtime_config)
    runtime_config["context"] = policy.model_dump(mode="json")
    return runtime_config


def context_policy_hash(policy: ContextPolicyV1 | dict) -> str:
    normalized = (
        policy.model_dump(mode="json")
        if isinstance(policy, ContextPolicyV1)
        else ContextPolicyV1.model_validate(policy).model_dump(mode="json")
    )
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
