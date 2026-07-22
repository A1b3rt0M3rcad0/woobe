from __future__ import annotations

from datetime import datetime
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
)
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class EvaluationTargetDecisionModel(BaseModel):
    __tablename__ = "target_decisions"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id",
            "target_id",
            "evidence_revision",
            name="uq_evaluation_target_decisions_run_target_revision",
        ),
        CheckConstraint(
            "decision IN ('accepted', 'rejected')",
            name="ck_evaluation_target_decisions_decision",
        ),
        CheckConstraint(
            "decision_basis IN ('evidence', 'manual_override')",
            name="ck_evaluation_target_decisions_basis",
        ),
        Index(
            "ix_evaluation_target_decisions_target",
            "project_id",
            "target_snapshot_hash",
            "decided_at",
        ),
        Index(
            "ix_evaluation_target_decisions_run",
            "evaluation_run_id",
            "decided_at",
        ),
        Index(
            "ix_evaluation_target_decisions_current",
            "evaluation_run_id",
            "target_id",
            "superseded_at",
            "evidence_revision",
        ),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.runs.id")
    )
    target_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.targets.id"))
    target_snapshot_hash: Mapped[str] = mapped_column(String(64))
    evidence_revision: Mapped[int] = mapped_column(Integer, default=1)
    assessment_hash: Mapped[str | None] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32))
    decision_basis: Mapped[str] = mapped_column(String(32), default="evidence")
    note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[UUID]
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_reason: Mapped[str | None] = mapped_column(Text)


__all__ = ["EvaluationTargetDecisionModel"]
