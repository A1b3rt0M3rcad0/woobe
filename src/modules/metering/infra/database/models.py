from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base, BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class UsageEventModel(BaseModel):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index(
            "uq_metering_usage_events_source_event",
            "source_event_id",
            unique=True,
            postgresql_where=text("source_event_id IS NOT NULL"),
        ),
        Index("ix_metering_usage_events_project_occurred", "project_id", "occurred_at"),
        Index("ix_metering_usage_events_project_trace", "project_id", "trace_id"),
        Index(
            "ix_metering_usage_events_project_agent_occurred",
            "project_id",
            "agent_id",
            "occurred_at",
        ),
        Index(
            "ix_metering_usage_events_project_network_occurred",
            "project_id",
            "network_id",
            "occurred_at",
        ),
        {"schema": "metering"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID | None]
    network_id: Mapped[UUID | None]
    network_execution_id: Mapped[UUID | None]
    network_version_id: Mapped[UUID | None]
    source_event_id: Mapped[UUID | None]
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trace_id: Mapped[UUID | None]
    call_id: Mapped[str | None] = mapped_column(String(128))
    environment: Mapped[str | None] = mapped_column(String(32))
    agent_release_id: Mapped[UUID | None]
    agent_release_version: Mapped[str | None] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(255))
    provider_model_id: Mapped[UUID | None]
    event_type: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    cost_status: Mapped[str | None] = mapped_column(String(32))
    cost_reason: Mapped[str | None] = mapped_column(Text)
    usage_complete: Mapped[bool | None] = mapped_column(Boolean)
    pricing_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    data: Mapped[dict | None] = mapped_column(JSONB)


class UsageDailyProjectModel(Base):
    __tablename__ = "usage_daily_project"
    __table_args__ = {"schema": "metering"}

    project_id: Mapped[UUID] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_requests: Mapped[int] = mapped_column(Integer, default=0)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    embedding_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    vector_queries: Mapped[int] = mapped_column(Integer, default=0)
    storage_mb: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    priced_requests: Mapped[int] = mapped_column(Integer, default=0)
    partial_cost_requests: Mapped[int] = mapped_column(Integer, default=0)
    unpriced_requests: Mapped[int] = mapped_column(Integer, default=0)
    last_event_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UsageDailyAgentModel(Base):
    __tablename__ = "usage_daily_agent"
    __table_args__ = {"schema": "metering"}

    agent_id: Mapped[UUID] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    requests: Mapped[int] = mapped_column(Integer, default=0)
    successful_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_requests: Mapped[int] = mapped_column(Integer, default=0)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    vector_queries: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    priced_requests: Mapped[int] = mapped_column(Integer, default=0)
    partial_cost_requests: Mapped[int] = mapped_column(Integer, default=0)
    unpriced_requests: Mapped[int] = mapped_column(Integer, default=0)
    last_event_occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
