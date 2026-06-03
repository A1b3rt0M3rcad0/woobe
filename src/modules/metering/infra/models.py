from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base, BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class UsageEventModel(BaseModel):
    __tablename__ = "usage_events"
    __table_args__ = {"schema": "metering"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai.agents.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    cost_usd: Mapped[float | None] = mapped_column(Float)
    data: Mapped[dict | None] = mapped_column(JSONB)


class UsageDailyProjectModel(Base):
    __tablename__ = "usage_daily_project"
    __table_args__ = {"schema": "metering"}

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.projects.id"), primary_key=True
    )
    day: Mapped[date] = mapped_column(primary_key=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    embedding_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    vector_queries: Mapped[int] = mapped_column(Integer, default=0)
    storage_mb: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime]


class UsageDailyAgentModel(Base):
    __tablename__ = "usage_daily_agent"
    __table_args__ = {"schema": "metering"}

    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai.agents.id"), primary_key=True
    )
    day: Mapped[date] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    vector_queries: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime]


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "metering"}


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = {"schema": "metering"}
