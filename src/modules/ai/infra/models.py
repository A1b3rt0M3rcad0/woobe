from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInbox
from shared.infra.database.outbox import OutboxEventModel as BaseOutbox


class ProviderCredentialModel(BaseModel):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("project_id", "provider", "name"),
        {"schema": "ai"},
    )

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    provider: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    encrypted_secret: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_validated_at: Mapped[datetime | None]


class AgentModel(BaseModel):
    __tablename__ = "agents"
    __table_args__ = {"schema": "ai"}

    project_id: Mapped[UUID] = mapped_column(ForeignKey("core.projects.id"))
    provider_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.provider_credentials.id")
    )
    fallback_credential_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ai.provider_credentials.id")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(64))
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(255))
    fallback_provider: Mapped[str | None] = mapped_column(String(64))
    fallback_model: Mapped[str | None] = mapped_column(String(255))
    temperature: Mapped[float | None] = mapped_column(Float)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    session_mode: Mapped[str] = mapped_column(String(32), default="stateless")
    status: Mapped[str] = mapped_column(String(32), default="active")
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class OutboxEventModel(BaseOutbox):
    __tablename__ = "outbox_events"
    __table_args__ = {"schema": "ai"}


class InboxEventModel(BaseInbox):
    __tablename__ = "inbox_events"
    __table_args__ = {"schema": "ai"}
