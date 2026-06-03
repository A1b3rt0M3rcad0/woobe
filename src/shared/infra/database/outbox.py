from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class OutboxEventModel(BaseModel):
    __abstract__ = True

    aggregate_type: Mapped[str] = mapped_column(String(128))
    aggregate_id: Mapped[UUID]
    event_type: Mapped[str] = mapped_column(String(255))
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(),
        server_default=text("now()"),
    )
    published_at: Mapped[datetime | None]
    error: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[UUID | None]
    causation_id: Mapped[UUID | None]
