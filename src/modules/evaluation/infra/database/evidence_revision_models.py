from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class EvaluationEvidenceRevisionModel(BaseModel):
    __tablename__ = "evidence_revisions"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_run_id",
            "revision",
            name="uq_evaluation_evidence_revisions_run_revision",
        ),
        Index(
            "ix_evaluation_evidence_revisions_project",
            "project_id",
            "created_at",
        ),
        Index(
            "ix_evaluation_evidence_revisions_run",
            "evaluation_run_id",
            "revision",
        ),
        {"schema": "evaluation"},
    )

    project_id: Mapped[UUID]
    evaluation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.runs.id")
    )
    revision: Mapped[int] = mapped_column(Integer)
    assessment_hash: Mapped[str | None] = mapped_column(String(64))
    evidence_status: Mapped[str] = mapped_column(String(32))
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    captured_reason: Mapped[str] = mapped_column(String(64))
    captured_by: Mapped[UUID | None]


__all__ = ["EvaluationEvidenceRevisionModel"]
