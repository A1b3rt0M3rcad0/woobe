from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class UserModel(BaseModel):
    __tablename__ = "users"
    __table_args__ = {"schema": "identity"}

    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(32), default="active")


class OrganizationModel(BaseModel):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug"), {"schema": "identity"})

    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")

    members: Mapped[list[OrganizationMemberModel]] = relationship(
        back_populates="organization"
    )


class OrganizationMemberModel(BaseModel):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        {"schema": "identity"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("identity.users.id"))
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.organizations.id")
    )
    role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    organization: Mapped[OrganizationModel] = relationship(back_populates="members")


class OrganizationInviteModel(BaseModel):
    __tablename__ = "organization_invites"
    __table_args__ = (
        UniqueConstraint("organization_id", "email"),
        {"schema": "identity"},
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.organizations.id")
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
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
