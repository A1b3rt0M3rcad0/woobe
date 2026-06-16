from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.time import utc_now
from shared.infra.database.base import BaseModel


class InboxEventModel(BaseModel):
    __abstract__ = True

    outbox_origin_id: Mapped[UUID | None]
    aggregate_type: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(255))
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=text("now()"),
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    consumer_name: Mapped[str | None] = mapped_column(String(128))
    correlation_id: Mapped[UUID | None]
    causation_id: Mapped[UUID | None]
