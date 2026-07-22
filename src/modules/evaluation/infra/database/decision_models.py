from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class EvaluationTargetDecisionModel(BaseModel):
    __tablename__ = "target_decisions"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id",
            "target_id",
            name="uq_evaluation_target_decisions_run_target",
        ),
        CheckConstraint(
            "decision IN ('accepted', 'rejected')",
            name="ck_evaluation_target_decisions_decision",
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
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.runs.id")
    )
    target_id: Mapped[UUID] = mapped_column(ForeignKey("evaluation.targets.id"))
    target_snapshot_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[UUID]
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


__all__ = ["EvaluationTargetDecisionModel"]
