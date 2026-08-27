from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from modules.context.domain.entities import ContextRetentionMode, ContextSourceType


class SessionContextPolicy(BaseModel):
    strategy: Literal["recent"] = "recent"
    max_messages: int = Field(default=20, ge=1, le=200)
    max_units: int | None = Field(default=None, ge=128, le=1_000_000)


class KnowledgeContextPolicy(BaseModel):
    max_units: int | None = Field(default=None, ge=128, le=1_000_000)


class ToolContextPolicy(BaseModel):
    max_result_units: int | None = Field(default=None, ge=64, le=1_000_000)


class DelegationContextPolicy(BaseModel):
    max_units: int | None = Field(default=None, ge=64, le=1_000_000)


class ContextBudgetPolicy(BaseModel):
    max_input_units: int | None = Field(default=None, ge=256, le=4_000_000)
    runtime_reserve_units: int = Field(default=0, ge=0, le=1_000_000)


class ContextRetentionPolicy(BaseModel):
    materialized_content: ContextRetentionMode = ContextRetentionMode.REFERENCES_ONLY


class ContextPressurePolicy(BaseModel):
    moderate_at: float = Field(default=0.40, gt=0, lt=1)
    high_at: float = Field(default=0.75, gt=0, lt=1)
    critical_at: float = Field(default=0.90, gt=0, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> "ContextPressurePolicy":
        if not self.moderate_at < self.high_at < self.critical_at:
            raise ValueError("context pressure thresholds must be strictly increasing")
        return self


class ContextPolicyV1(BaseModel):
    schema_version: Literal[1] = 1
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
    session: SessionContextPolicy = Field(default_factory=SessionContextPolicy)
    knowledge: KnowledgeContextPolicy = Field(default_factory=KnowledgeContextPolicy)
    tools: ToolContextPolicy = Field(default_factory=ToolContextPolicy)
    delegation: DelegationContextPolicy = Field(default_factory=DelegationContextPolicy)
    budget: ContextBudgetPolicy = Field(default_factory=ContextBudgetPolicy)
    retention: ContextRetentionPolicy = Field(default_factory=ContextRetentionPolicy)
    pressure: ContextPressurePolicy = Field(default_factory=ContextPressurePolicy)


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
