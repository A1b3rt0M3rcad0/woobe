from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class TraceModel(BaseModel):
    __tablename__ = "traces"
    __table_args__ = {"schema": "observability"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai.agents.id"))
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("runtime.sessions.id")
    )
    external_session_id: Mapped[str | None] = mapped_column(String(255))
    tenant_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    total_latency_ms: Mapped[float | None] = mapped_column(Float)
    total_cost_usd: Mapped[float | None] = mapped_column(Float)
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    fallback_used: Mapped[bool] = mapped_column(default=False)
    error: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)


class TraceEventModel(BaseModel):
    __tablename__ = "trace_events"
    __table_args__ = {"schema": "observability"}

    trace_id: Mapped[UUID] = mapped_column(ForeignKey("observability.traces.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    payload_ref: Mapped[str | None] = mapped_column(String(512))


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "observability"}


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = {"schema": "observability"}
