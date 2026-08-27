from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class ModelInvocationModel(BaseModel):
    __tablename__ = "model_invocations"
    __table_args__ = (
        Index("ix_context_invocations_run_call", "agent_run_id", "call_index"),
        Index("ix_context_invocations_project_created", "project_id", "created_at"),
        Index("ix_context_invocations_trace", "trace_id"),
        Index("ix_context_invocations_network_execution", "network_execution_id", "created_at"),
        {"schema": "context"},
    )

    project_id: Mapped[UUID]
    # Cross-bounded-context causality is identifier-only. Context owns no Agent rows.
    agent_run_id: Mapped[UUID]
    agent_id: Mapped[UUID]
    trace_id: Mapped[UUID | None] = mapped_column(nullable=True)
    network_execution_id: Mapped[UUID | None] = mapped_column(nullable=True)
    network_invocation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    call_index: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(96))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    provider_model_id: Mapped[UUID | None] = mapped_column(nullable=True)
    provider_credential_id: Mapped[UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    output_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    usage_complete: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ContextSnapshotModel(BaseModel):
    __tablename__ = "context_snapshots"
    __table_args__ = (
        UniqueConstraint("model_invocation_id", name="uq_context_snapshot_model_invocation"),
        Index("ix_context_snapshots_run_created", "agent_run_id", "created_at"),
        Index("ix_context_snapshots_project_created", "project_id", "created_at"),
        {"schema": "context"},
    )

    project_id: Mapped[UUID]
    model_invocation_id: Mapped[UUID] = mapped_column(
        ForeignKey("context.model_invocations.id", ondelete="CASCADE")
    )
    # Identifier-only link to AgentRun; no cross-module FK.
    agent_run_id: Mapped[UUID]
    policy_schema_version: Mapped[int] = mapped_column(Integer)
    policy_hash: Mapped[str] = mapped_column(String(64))
    model_capacity_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reserved_output_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    runtime_reserve_units: Mapped[int] = mapped_column(BigInteger, default=0)
    usable_input_budget: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    estimated_input_units: Mapped[int] = mapped_column(BigInteger)
    reported_input_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    utilization: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure_status: Mapped[str] = mapped_column(String(32))
    measurement_status: Mapped[str] = mapped_column(String(32))
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    materialized_hash: Mapped[str] = mapped_column(String(64))
    retention_mode: Mapped[str] = mapped_column(String(32))
    reproduction_level: Mapped[str] = mapped_column(String(32))


class ContextContributionModel(BaseModel):
    __tablename__ = "context_contributions"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "ordinal", name="uq_context_contribution_ordinal"),
        Index("ix_context_contributions_snapshot", "snapshot_id", "ordinal"),
        Index("ix_context_contributions_source", "source_type", "source_ref"),
        {"schema": "context"},
    )

    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("context.context_snapshots.id", ondelete="CASCADE")
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parent_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    modality: Mapped[str] = mapped_column(String(32), default="text")
    priority: Mapped[str] = mapped_column(String(32))
    raw_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    materialized_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    selection_method: Mapped[str | None] = mapped_column(String(96), nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    transformations: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    trust: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sensitivity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    integrity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
