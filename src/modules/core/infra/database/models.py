from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base, BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class SecurityRateLimitEventModel(Base):
    __tablename__ = "security_rate_limit_events"
    __table_args__ = (
        Index(
            "ix_security_rate_limit_events_window",
            "namespace",
            "subject_key",
            "occurred_at",
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    namespace: Mapped[str] = mapped_column(String(64))
    subject_key: Mapped[str] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class SecurityConcurrencyLeaseModel(Base):
    __tablename__ = "security_concurrency_leases"
    __table_args__ = (
        Index(
            "ix_security_concurrency_leases_subject",
            "namespace",
            "subject_key",
            "expires_at",
        ),
        Index(
            "ix_security_concurrency_leases_expiry",
            "expires_at",
        ),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    namespace: Mapped[str] = mapped_column(String(64))
    subject_key: Mapped[str] = mapped_column(String(255))
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
        Index("ix_core_api_keys_credential_created", "credential_id", "created_at"),
        Index(
            "ix_core_api_keys_runtime_binding",
            "project_id",
            "kind",
            "agent_id",
            "environment",
            "status",
        ),
        Index(
            "ix_core_api_keys_runtime_target_binding",
            "project_id",
            "kind",
            "target_type",
            "target_id",
            "environment",
            "status",
        ),
        CheckConstraint(
            "(kind = 'project' AND agent_id IS NULL AND target_type IS NULL "
            "AND target_id IS NULL AND environment IS NULL) OR "
            "(kind = 'runtime' AND target_type = 'agent' AND target_id IS NOT NULL "
            "AND agent_id = target_id AND environment IN ('staging', 'production')) OR "
            "(kind = 'runtime' AND target_type = 'network' AND target_id IS NOT NULL "
            "AND agent_id IS NULL AND environment IN ('staging', 'production'))",
            name="ck_core_api_keys_runtime_binding",
        ),
        {"schema": "core"},
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    credential_id: Mapped[UUID] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    key_prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    key_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    kind: Mapped[str] = mapped_column(String(32), default="project")
    agent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    environment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    interfaces: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[UUID]
    rotated_from_id: Mapped[UUID | None] = mapped_column(nullable=True)


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
