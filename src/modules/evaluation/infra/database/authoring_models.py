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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class EvaluationAuthoringAttemptModel(BaseModel):
    __tablename__ = "authoring_attempts"
    __table_args__ = (
        Index(
            "ix_evaluation_authoring_attempts_call_created",
            "authoring_call_id",
            "created_at",
        ),
        Index(
            "ix_evaluation_authoring_attempts_project_status",
            "project_id",
            "status",
            "created_at",
        ),
        {"schema": "evaluation"},
    )

    authoring_call_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.authoring_calls.id")
    )
    authoring_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation.authoring_batches.id")
    )
    project_id: Mapped[UUID]
    provider_model_id: Mapped[UUID]
    provider_credential_id: Mapped[UUID]
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    context_hash: Mapped[str] = mapped_column(String(64))
    requested_slot_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(18, 10))
    pricing_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_category: Mapped[str | None] = mapped_column(String(128))
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationAuthoringCaseSlotModel(BaseModel):
    __tablename__ = "authoring_case_slots"
    __table_args__ = (
        UniqueConstraint(
            "authoring_call_id",
            "position",
            name="uq_evaluation_authoring_case_slots_position",
        ),
        CheckConstraint(
            "position > 0",
            name="ck_evaluation_authoring_case_slots_position",
        ),
        Index(
            "ix_evaluation_authoring_case_slots_call_status",
            "authoring_call_id",
            "status",
            "position",
        ),
        Index(
            "ix_evaluation_authoring_case_slots_batch_position",
            "authoring_batch_id",
            "position",
        ),
        {"schema": "evaluation"},
    )

    authoring_call_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.authoring_calls.id")
    )
    authoring_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.authoring_batches.id")
    )
    project_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(Integer)
    coverage_category: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="planned")
    name: Mapped[str | None] = mapped_column(String(255))
    generated_case: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    failure_category: Mapped[str | None] = mapped_column(String(128))
    recommended_action: Mapped[str | None] = mapped_column(String(128))
    source_attempt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation.authoring_attempts.id")
    )


@event.listens_for(EvaluationAuthoringAttemptModel, "before_insert")
def _populate_attempt_context_hash(mapper, connection, target) -> None:
    del mapper
    if target.context_hash:
        return
    from modules.evaluation.infra.database.models import EvaluationAuthoringCallModel

    target.context_hash = connection.execute(
        select(EvaluationAuthoringCallModel.context_hash).where(
            EvaluationAuthoringCallModel.id == target.authoring_call_id
        )
    ).scalar_one()


__all__ = [
    "EvaluationAuthoringAttemptModel",
    "EvaluationAuthoringCaseSlotModel",
]
