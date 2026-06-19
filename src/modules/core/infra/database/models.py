from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class ProjectModel(BaseModel):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug"),
        {"schema": "core"},
    )

    organization_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class ApiKeyModel(BaseModel):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_core_api_keys_prefix_status", "key_prefix", "status"),
        {"schema": "core"},
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    name: Mapped[str] = mapped_column(String(255))
    key_prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    key_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID]
    rotated_from_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.api_keys.id"),
        nullable=True,
    )


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_core_outbox_idempotency_key"),
        Index(
            "ix_core_outbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('pending', 'retryable')"),
        ),
        Index("ix_core_outbox_correlation_id", "correlation_id"),
        Index("ix_core_outbox_aggregate", "aggregate_type", "aggregate_id"),
        {"schema": "core"},
    )


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_core_inbox_message_id"),
        UniqueConstraint("idempotency_key", name="uq_core_inbox_idempotency_key"),
        Index(
            "ix_core_inbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('received', 'retryable')"),
        ),
        Index("ix_core_inbox_correlation_id", "correlation_id"),
        {"schema": "core"},
    )
