from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, LargeBinary, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from shared.infra.database.base import BaseModel


class AdministrativeOperationModel(BaseModel):
    __tablename__ = "administrative_operations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "actor",
            "operation",
            "key_digest",
            name="uq_core_administrative_operation",
        ),
        Index("ix_core_administrative_operation_expiry", "expires_at"),
        {"schema": "core"},
    )
    workspace_id: Mapped[UUID]
    actor: Mapped[str] = mapped_column(String(96))
    operation: Mapped[str] = mapped_column(String(128))
    key_digest: Mapped[bytes] = mapped_column(LargeBinary)
    payload_digest: Mapped[bytes] = mapped_column(LargeBinary)
    response_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
