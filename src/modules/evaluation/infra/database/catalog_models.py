from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class EvaluationModel(BaseModel):
    __tablename__ = "evaluations"
    __table_args__ = (
        Index(
            "uq_evaluation_catalog_protocol_identity",
            "project_id",
            "suite_version_id",
            "target_identity_hash",
            "evaluation_protocol_hash",
            unique=True,
            postgresql_where=text("evaluation_protocol_hash IS NOT NULL"),
        ),
        Index(
            "uq_evaluation_catalog_legacy_identity",
            "project_id",
            "suite_version_id",
            "target_identity_hash",
            unique=True,
            postgresql_where=text("evaluation_protocol_hash IS NULL"),
        ),
        Index(
            "ix_evaluation_catalog_entity",
            "project_id",
            "target_type",
            "entity_id",
            "updated_at",
        ),
        Index(
            "ix_evaluation_catalog_snapshot",
            "project_id",
            "target_snapshot_hash",
            "suite_version_id",
        ),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    suite_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.suite_versions.id")
    )
    evaluation_protocol_hash: Mapped[str | None] = mapped_column(String(64))
    target_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[UUID]
    source_type: Mapped[str] = mapped_column(String(32))
    target_version_id: Mapped[UUID | None]
    target_snapshot_hash: Mapped[str] = mapped_column(String(64))
    target_identity_hash: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(255))
    display_version: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")
    latest_run_id: Mapped[UUID | None]
    created_by: Mapped[UUID | None]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[UUID | None]


class EvaluationComparisonModel(BaseModel):
    __tablename__ = "comparisons"
    __table_args__ = (
        CheckConstraint(
            "candidate_run_id <> reference_run_id",
            name="ck_evaluation_comparisons_distinct_runs",
        ),
        UniqueConstraint(
            "candidate_run_id",
            "candidate_evidence_revision",
            "reference_run_id",
            "reference_evidence_revision",
            name="uq_evaluation_comparison_evidence_pair",
        ),
        Index(
            "ix_evaluation_comparisons_project_created",
            "project_id",
            "created_at",
        ),
        Index(
            "ix_evaluation_comparisons_status",
            "status",
            "updated_at",
        ),
        Index(
            "uq_evaluation_comparisons_project_idempotency",
            "project_id",
            "request_idempotency_key",
            unique=True,
            postgresql_where=text("request_idempotency_key IS NOT NULL"),
        ),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    suite_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.suite_versions.id")
    )
    protocol_hash: Mapped[str] = mapped_column(String(64))
    comparison_mode: Mapped[str] = mapped_column(String(32))
    candidate_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.runs.id"))
    candidate_evidence_revision: Mapped[int] = mapped_column(Integer, default=1)
    reference_run_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.runs.id"))
    reference_evidence_revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32), default="waiting")
    aggregate_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None] = mapped_column(String(128))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    request_idempotency_key: Mapped[str | None] = mapped_column(String(255))
    requested_by: Mapped[UUID | None]
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationComparisonDecisionModel(BaseModel):
    __tablename__ = "comparison_decisions"
    __table_args__ = (
        UniqueConstraint(
            "comparison_id",
            "candidate_evidence_revision",
            "reference_evidence_revision",
            name="uq_evaluation_comparison_decision_revisions",
        ),
        Index(
            "ix_evaluation_comparison_decisions_project",
            "project_id",
            "decided_at",
        ),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    comparison_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.comparisons.id")
    )
    candidate_evidence_revision: Mapped[int] = mapped_column(Integer)
    reference_evidence_revision: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(32))
    decision_basis: Mapped[str] = mapped_column(String(32), default="evidence")
    note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[UUID]
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


__all__ = [
    "EvaluationModel",
    "EvaluationComparisonModel",
    "EvaluationComparisonDecisionModel",
]
