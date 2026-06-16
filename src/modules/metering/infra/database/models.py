from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import Index, UniqueConstraint, text

from shared.infra.database.base import Base, BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class UsageEventModel(BaseModel):
    __tablename__ = "usage_events"
    __table_args__ = {"schema": "metering"}

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID | None]
    event_type: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    cost_usd: Mapped[float | None] = mapped_column(Float)
    data: Mapped[dict | None] = mapped_column(JSONB)


class UsageDailyProjectModel(Base):
    __tablename__ = "usage_daily_project"
    __table_args__ = {"schema": "metering"}

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    embedding_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    vector_queries: Mapped[int] = mapped_column(Integer, default=0)
    storage_mb: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UsageDailyAgentModel(Base):
    __tablename__ = "usage_daily_agent"
    __table_args__ = {"schema": "metering"}

    agent_id: Mapped[UUID] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    vector_queries: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_metering_outbox_idempotency_key"),
        Index(
            "ix_metering_outbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('pending', 'retryable')"),
        ),
        Index("ix_metering_outbox_correlation_id", "correlation_id"),
        Index("ix_metering_outbox_aggregate", "aggregate_type", "aggregate_id"),
        {"schema": "metering"},
    )


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_metering_inbox_message_id"),
        UniqueConstraint("idempotency_key", name="uq_metering_inbox_idempotency_key"),
        Index(
            "ix_metering_inbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('received', 'retryable')"),
        ),
        Index("ix_metering_inbox_correlation_id", "correlation_id"),
        {"schema": "metering"},
    )
