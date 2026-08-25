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


class ChatSurfaceModel(BaseModel):
    __tablename__ = "chat_surfaces"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_chat_surface_public_id"),
        UniqueConstraint(
            "project_id",
            "normalized_name",
            name="uq_chat_surface_project_name",
        ),
        Index(
            "ix_chat_surface_project_status",
            "project_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_chat_surface_target",
            "project_id",
            "target_type",
            "target_id",
            "status",
        ),
        Index(
            "ix_chat_surface_release",
            "project_id",
            "target_type",
            "target_release_id",
            "status",
        ),
        CheckConstraint(
            "target_type IN ('agent', 'network')",
            name="ck_chat_surface_target_type",
        ),
        CheckConstraint(
            "environment = 'production'",
            name="ck_chat_surface_production_only",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'disabled', 'archived')",
            name="ck_chat_surface_status",
        ),
        CheckConstraint(
            "session_token_ttl_seconds BETWEEN 60 AND 3600",
            name="ck_chat_surface_token_ttl",
        ),
        {"schema": "chat_surface"},
    )

    public_id: Mapped[str] = mapped_column(String(32))
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.projects.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[UUID]
    target_release_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(
        String(16),
        default="production",
        server_default=text("'production'"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="draft",
        server_default=text("'draft'"),
    )
    access_mode: Mapped[str] = mapped_column(
        String(32),
        default="backend_managed",
        server_default=text("'backend_managed'"),
    )
    allowed_origins: Mapped[list[str]] = mapped_column(JSONB, default=list)
    appearance_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    requests_per_minute: Mapped[int] = mapped_column(
        Integer,
        default=30,
        server_default=text("30"),
    )
    max_concurrent_runs: Mapped[int] = mapped_column(
        Integer,
        default=10,
        server_default=text("10"),
    )
    session_token_ttl_seconds: Mapped[int] = mapped_column(
        Integer,
        default=900,
        server_default=text("900"),
    )
    token_epoch: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
    )
    created_by: Mapped[UUID | None] = mapped_column(nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ChatSurfaceSessionBindingModel(BaseModel):
    __tablename__ = "session_bindings"
    __table_args__ = (
        UniqueConstraint(
            "chat_surface_id",
            "session_id",
            name="uq_chat_surface_session",
        ),
        UniqueConstraint(
            "chat_surface_id",
            "idempotency_key",
            name="uq_chat_surface_session_idempotency",
        ),
        Index(
            "ix_chat_surface_session_activity",
            "chat_surface_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_chat_surface_session_release",
            "target_type",
            "target_release_id",
            "status",
        ),
        CheckConstraint(
            "target_type IN ('agent', 'network')",
            name="ck_chat_surface_session_target_type",
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'blocked')",
            name="ck_chat_surface_session_status",
        ),
        {"schema": "chat_surface"},
    )

    chat_surface_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_surface.chat_surfaces.id", ondelete="CASCADE")
    )
    project_id: Mapped[UUID]
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[UUID]
    target_release_id: Mapped[UUID]
    session_id: Mapped[UUID]
    surface_credential_id: Mapped[UUID]
    idempotency_key: Mapped[str] = mapped_column(String(255))
    external_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="active",
        server_default=text("'active'"),
    )


class ChatSurfaceMessageRequestModel(BaseModel):
    __tablename__ = "message_requests"
    __table_args__ = (
        UniqueConstraint(
            "session_binding_id",
            "idempotency_key",
            name="uq_chat_surface_message_idempotency",
        ),
        Index(
            "uq_chat_surface_active_message",
            "session_binding_id",
            unique=True,
            postgresql_where=text("status IN ('accepted', 'streaming')"),
        ),
        CheckConstraint(
            "status IN ('accepted', 'streaming', 'completed', 'failed', 'cancelled')",
            name="ck_chat_surface_message_status",
        ),
        {"schema": "chat_surface"},
    )

    session_binding_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_surface.session_bindings.id", ondelete="CASCADE")
    )
    idempotency_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32),
        default="accepted",
        server_default=text("'accepted'"),
    )
    target_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
