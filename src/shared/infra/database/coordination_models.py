from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import Base


class RequestWindowEventModel(Base):
    __tablename__ = "security_rate_limit_events"
    __table_args__ = (
        Index(
            "ix_security_rate_limit_events_window",
            "namespace",
            "subject_key",
            "occurred_at",
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    namespace: Mapped[str] = mapped_column(String(64))
    subject_key: Mapped[str] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class ExecutionLeaseModel(Base):
    __tablename__ = "security_concurrency_leases"
    __table_args__ = (
        Index(
            "ix_security_concurrency_leases_subject",
            "namespace",
            "subject_key",
            "expires_at",
        ),
        Index(
            "ix_security_concurrency_leases_expiry",
            "expires_at",
        ),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    namespace: Mapped[str] = mapped_column(String(64))
    subject_key: Mapped[str] = mapped_column(String(255))
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
