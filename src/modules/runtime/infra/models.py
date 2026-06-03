from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class SessionModel(BaseModel):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("project_id", "agent_id", "external_session_id"),
        {"schema": "runtime"},
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    external_session_id: Mapped[str | None] = mapped_column(String(255))
    tenant_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")
    mode: Mapped[str] = mapped_column(String(32), default="chat")
    data: Mapped[dict | None] = mapped_column(JSONB)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageModel(BaseModel):
    __tablename__ = "messages"
    __table_args__ = {"schema": "runtime"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("ai.agents.id"))
    session_id: Mapped[UUID] = mapped_column(ForeignKey("runtime.sessions.id"))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 8))
    data: Mapped[dict | None] = mapped_column(JSONB)


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "runtime"}


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = {"schema": "runtime"}
