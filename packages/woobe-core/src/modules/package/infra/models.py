from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    JSON,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class PackageUploadModel(BaseModel):
    __tablename__ = "uploads"
    __table_args__ = (
        Index("ix_package_upload_expiry", "expires_at"),
        {"schema": "package"},
    )
    project_id: Mapped[UUID] = mapped_column()
    actor: Mapped[str] = mapped_column(String(96))
    artifact_digest: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512))
    manifest: Mapped[dict] = mapped_column(JSON)
    inventory: Mapped[list] = mapped_column(JSON)
    size_bytes: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PackagePlanModel(BaseModel):
    __tablename__ = "plans"
    __table_args__ = (
        Index("ix_package_plan_expiry", "expires_at"),
        {"schema": "package"},
    )
    project_id: Mapped[UUID] = mapped_column()
    actor: Mapped[str] = mapped_column(String(96))
    upload_id: Mapped[UUID] = mapped_column()
    artifact_digest: Mapped[str] = mapped_column(String(64))
    plan_digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PackageOperationModel(BaseModel):
    __tablename__ = "operations"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "actor", "key_digest", name="uq_package_operation_identity"
        ),
        Index("ix_package_operation_claim", "state", "lease_until"),
        {"schema": "package"},
    )
    project_id: Mapped[UUID] = mapped_column()
    actor: Mapped[str] = mapped_column(String(96))
    key_digest: Mapped[bytes] = mapped_column(LargeBinary)
    # HMAC is private server evidence, never part of status or plan responses.
    payload_fingerprint: Mapped[bytes] = mapped_column(LargeBinary)
    payload_ciphertext: Mapped[str] = mapped_column(Text)
    principal_ciphertext: Mapped[str] = mapped_column(Text)
    artifact_digest: Mapped[str] = mapped_column(String(64))
    upload_id: Mapped[UUID] = mapped_column()
    plan_id: Mapped[UUID] = mapped_column()
    lifecycle: Mapped[str] = mapped_column(String(16))
    lifecycle_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="accepted")
    phase: Mapped[str | None] = mapped_column(String(160), nullable=True)
    phases_completed: Mapped[int] = mapped_column(Integer, default=0)
    phases_total: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    configuration_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    inventory: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    diagnostics: Mapped[list] = mapped_column(JSON, default=list)
    lease_token: Mapped[UUID | None] = mapped_column(nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PackageEffectModel(BaseModel):
    __tablename__ = "effects"
    __table_args__ = (
        UniqueConstraint("operation_id", "phase", name="uq_package_effect_phase"),
        {"schema": "package"},
    )
    operation_id: Mapped[UUID] = mapped_column()
    phase: Mapped[str] = mapped_column(String(160))
    response_ciphertext: Mapped[str] = mapped_column(Text)


class PackageExportModel(BaseModel):
    __tablename__ = "exports"
    __table_args__ = (
        Index("ix_package_export_expiry", "expires_at"),
        {"schema": "package"},
    )
    project_id: Mapped[UUID] = mapped_column()
    actor: Mapped[str] = mapped_column(String(96))
    source: Mapped[dict] = mapped_column(JSON)
    artifact_digest: Mapped[str] = mapped_column(String(64))
    transport_digest: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer)
    inventory: Mapped[list] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
