from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class ToolModel(BaseModel):
    __tablename__ = "tools"
    __table_args__ = {"schema": "tools"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai.agents.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict | None] = mapped_column(JSONB)
    input_schema: Mapped[dict | None] = mapped_column(JSONB)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)
    risk_level: Mapped[str] = mapped_column(String(32), default="low")
    timeout_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="active")


class SecretModel(BaseModel):
    __tablename__ = "secrets"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        {"schema": "tools"},
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64))
    encrypted_value: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB)


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "tools"}


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = {"schema": "tools"}
