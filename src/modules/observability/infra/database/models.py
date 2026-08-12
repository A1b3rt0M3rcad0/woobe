from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class TraceModel(BaseModel):
    __tablename__ = "traces"
    __table_args__ = (
        Index(
            "ix_observability_traces_project_started_terminal",
            "project_id",
            "started_at",
            postgresql_where=text("status IN ('completed', 'failed', 'cancelled')"),
        ),
        Index(
            "ix_observability_traces_project_network_started",
            "project_id",
            "network_id",
            "started_at",
        ),
        Index("ix_observability_traces_provider_model_id", "provider_model_id"),
        Index("ix_observability_traces_provider_credential_id", "provider_credential_id"),
        Index("ix_observability_traces_fallback_provider_model_id", "fallback_provider_model_id"),
        {"schema": "observability"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID | None]
    session_id: Mapped[UUID | None]
    network_id: Mapped[UUID | None]
    network_execution_id: Mapped[UUID | None]
    network_session_id: Mapped[UUID | None]
    network_version_id: Mapped[UUID | None]
    external_session_id: Mapped[str | None] = mapped_column(String(255))
    tenant_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_latency_ms: Mapped[float | None] = mapped_column(Float)
    total_cost_usd: Mapped[float | None] = mapped_column(Float)
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    provider_model_id: Mapped[UUID | None]
    provider_credential_id: Mapped[UUID | None]
    fallback_provider_model_id: Mapped[UUID | None]
    fallback_credential_id: Mapped[UUID | None]
    fallback_used: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)


class TraceEventModel(BaseModel):
    __tablename__ = "trace_events"
    __table_args__ = (
        Index(
            "ix_observability_trace_events_project_created_tool",
            "project_id",
            "created_at",
            postgresql_where=text("event_type = 'tool_call'"),
        ),
        {"schema": "observability"},
    )

    trace_id: Mapped[UUID] = mapped_column(ForeignKey("observability.traces.id"))
    project_id: Mapped[UUID]
    event_type: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    payload_ref: Mapped[str | None] = mapped_column(String(512))


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_observability_outbox_idempotency_key"),
        Index(
            "ix_observability_outbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('pending', 'retryable')"),
        ),
        Index("ix_observability_outbox_correlation_id", "correlation_id"),
        Index("ix_observability_outbox_aggregate", "aggregate_type", "aggregate_id"),
        {"schema": "observability"},
    )


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_observability_inbox_message_id"),
        UniqueConstraint("idempotency_key", name="uq_observability_inbox_idempotency_key"),
        Index(
            "ix_observability_inbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('received', 'retryable')"),
        ),
        Index("ix_observability_inbox_correlation_id", "correlation_id"),
        {"schema": "observability"},
    )
