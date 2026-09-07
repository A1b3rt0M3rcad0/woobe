from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

import uuid6


class ContextSourceType(StrEnum):
    SKILL = "SKILL"
    SYSTEM = "SYSTEM"
    USER_INPUT = "USER_INPUT"
    SESSION = "SESSION"
    CHECKPOINT = "CHECKPOINT"
    MEMORY = "MEMORY"
    KNOWLEDGE = "KNOWLEDGE"
    TOOL = "TOOL"
    ARTIFACT = "ARTIFACT"
    DELEGATION = "DELEGATION"
    RUNTIME = "RUNTIME"


class ContextPriority(StrEnum):
    MANDATORY = "MANDATORY"
    HIGH = "HIGH"
    DYNAMIC = "DYNAMIC"
    OPTIONAL = "OPTIONAL"
    DISCARDABLE = "DISCARDABLE"


class ContextRetentionMode(StrEnum):
    REFERENCES_ONLY = "references_only"
    REDACTED = "redacted"
    FULL = "full"


class ContextMeasurementStatus(StrEnum):
    ESTIMATED = "estimated"
    REPORTED = "reported"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ContextPressureStatus(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class ContextReproductionLevel(StrEnum):
    INPUT_REPRODUCIBLE = "input_reproducible"
    MANIFEST_ONLY = "manifest_only"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class ContextContribution:
    snapshot_id: UUID
    ordinal: int
    source_type: ContextSourceType
    modality: str = "text"
    priority: ContextPriority = ContextPriority.DYNAMIC
    source_ref: str | None = None
    parent_ref: str | None = None
    raw_units: int | None = None
    materialized_units: int | None = None
    selection_method: str | None = None
    relevance_score: float | None = None
    transformations: tuple[str, ...] = ()
    trust: str | None = None
    sensitivity: str | None = None
    integrity_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid6.uuid7)


@dataclass(frozen=True, slots=True)
class ContextSnapshot:
    project_id: UUID
    model_invocation_id: UUID
    agent_run_id: UUID
    policy_schema_version: int
    policy_hash: str
    estimated_input_units: int
    manifest: dict[str, Any]
    materialized_hash: str
    retention_mode: ContextRetentionMode
    reproduction_level: ContextReproductionLevel
    model_capacity_units: int | None = None
    reserved_output_units: int | None = None
    runtime_reserve_units: int = 0
    usable_input_budget: int | None = None
    reported_input_units: int | None = None
    utilization: float | None = None
    pressure_status: ContextPressureStatus = ContextPressureStatus.UNKNOWN
    measurement_status: ContextMeasurementStatus = ContextMeasurementStatus.ESTIMATED
    contributions: tuple[ContextContribution, ...] = ()
    id: UUID = field(default_factory=uuid6.uuid7)
