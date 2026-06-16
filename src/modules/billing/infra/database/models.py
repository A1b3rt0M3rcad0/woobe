from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class PlanModel(BaseModel):
    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("code"), {"schema": "billing"})

    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    price_usd: Mapped[float] = mapped_column(Float)
    billing_interval: Mapped[str] = mapped_column(String(32))
    limits: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="active")


class CustomerModel(BaseModel):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("provider", "provider_customer_id"),
        {"schema": "billing"},
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.organizations.id")
    )
    provider: Mapped[str] = mapped_column(String(64))
    provider_customer_id: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    data: Mapped[dict | None] = mapped_column(JSONB)


class SubscriptionModel(BaseModel):
    __tablename__ = "subscriptions"
    __table_args__ = {"schema": "billing"}

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("identity.organizations.id")
    )
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("billing.customers.id"))
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("billing.plans.id"))
    provider: Mapped[str] = mapped_column(String(64))
    provider_subscription_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEventModel(BaseModel):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id"),
        {"schema": "billing"},
    )

    provider: Mapped[str] = mapped_column(String(64))
    provider_event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_billing_outbox_idempotency_key"),
        Index(
            "ix_billing_outbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('pending', 'retryable')"),
        ),
        Index("ix_billing_outbox_correlation_id", "correlation_id"),
        Index("ix_billing_outbox_aggregate", "aggregate_type", "aggregate_id"),
        {"schema": "billing"},
    )


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_billing_inbox_message_id"),
        UniqueConstraint("idempotency_key", name="uq_billing_inbox_idempotency_key"),
        Index(
            "ix_billing_inbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('received', 'retryable')"),
        ),
        Index("ix_billing_inbox_correlation_id", "correlation_id"),
        {"schema": "billing"},
    )
