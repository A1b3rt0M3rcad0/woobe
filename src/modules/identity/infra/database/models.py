from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.infra.database.base import Base, BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class UserModel(BaseModel):
    __tablename__ = "users"
    __table_args__ = {"schema": "identity"}

    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(32), default="active")


class WorkspaceModel(BaseModel):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("slug"), {"schema": "identity"})

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")

    members: Mapped[list[WorkspaceMemberModel]] = relationship(
        back_populates="workspace"
    )


class WorkspaceMemberModel(BaseModel):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        {"schema": "identity"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"))
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.workspaces.id")
    )
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    workspace: Mapped[WorkspaceModel] = relationship(back_populates="members")


class WorkspaceInviteModel(BaseModel):
    __tablename__ = "workspace_invites"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email"),
        {"schema": "identity"},
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.workspaces.id")
    )
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(255))
    invited_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSessionModel(BaseModel):
    __tablename__ = "user_sessions"
    __table_args__ = {"schema": "identity"}

    user_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"))
    refresh_token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    replaced_by_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity.user_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InstanceSettingsModel(Base):
    __tablename__ = "instance_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_identity_instance_singleton"),
        CheckConstraint(
            "signup_mode IN ('open', 'invite_only', 'disabled')",
            name="ck_identity_instance_signup_mode",
        ),
        {"schema": "identity"},
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("identity.users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    initialized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    signup_mode: Mapped[str] = mapped_column(
        String(32), default="invite_only", server_default="invite_only"
    )
    telemetry_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_identity_outbox_idempotency_key"),
        Index(
            "ix_identity_outbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('pending', 'retryable')"),
        ),
        Index("ix_identity_outbox_correlation_id", "correlation_id"),
        Index("ix_identity_outbox_aggregate", "aggregate_type", "aggregate_id"),
        {"schema": "identity"},
    )


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_identity_inbox_message_id"),
        UniqueConstraint("idempotency_key", name="uq_identity_inbox_idempotency_key"),
        Index(
            "ix_identity_inbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('received', 'retryable')"),
        ),
        Index("ix_identity_inbox_correlation_id", "correlation_id"),
        {"schema": "identity"},
    )
