"""Core owns Project lifecycle authority and append-only policy changes."""
from uuid import UUID
from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from shared.infra.database.base import BaseModel

_JSON = JSON().with_variant(JSONB(), "postgresql")

class ProjectLifecyclePolicyModel(BaseModel):
    __tablename__ = "asac_project_lifecycle_policies"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_core_asac_policy_project"),
        CheckConstraint("generation >= 1", name="ck_core_asac_policy_generation"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="RESTRICT"))
    generation: Mapped[int] = mapped_column(BigInteger)
    managed: Mapped[bool] = mapped_column(Boolean, default=False)
    production_actors: Mapped[list] = mapped_column(_JSON, default=list)

class ProjectLifecyclePolicyOperationModel(BaseModel):
    __tablename__ = "asac_project_lifecycle_operations"
    __table_args__ = (
        UniqueConstraint("operation_id", name="uq_core_asac_policy_operation"),
        {"schema": "core"},
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id", ondelete="RESTRICT"))
    operation_id: Mapped[UUID]
    actor: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(71))
    reason: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(_JSON)
    outbox_id: Mapped[UUID] = mapped_column(ForeignKey("core.outbox_events.id", deferrable=True, initially="DEFERRED"))
