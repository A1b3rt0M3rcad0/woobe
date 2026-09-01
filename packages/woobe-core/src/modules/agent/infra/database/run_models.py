from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel


class AgentRunModel(BaseModel):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled', 'uncertain')",
            name="ck_agent_runs_status",
        ),
        Index(
            "ix_agent_runs_project_status_created",
            "project_id",
            "status",
            "created_at",
        ),
        Index("ix_agent_runs_agent_created", "agent_id", "created_at"),
        Index("ix_agent_runs_session_created", "session_id", "created_at"),
        Index(
            "ix_agent_runs_network_execution",
            "network_execution_id",
            "created_at",
        ),
        Index("ix_agent_runs_trace", "trace_id"),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agent.agents.id"))
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.sessions.id"),
        nullable=True,
    )
    agent_release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_releases.id"),
        nullable=True,
    )
    input_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.messages.id"),
        nullable=True,
    )
    output_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.messages.id"),
        nullable=True,
    )
    trace_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(32))
    origin: Mapped[str] = mapped_column(String(64), default="runtime_api")
    status: Mapped[str] = mapped_column(String(32), default="running")
    input_message: Mapped[str] = mapped_column(Text)
    execution_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cross-bounded-context causality is intentionally identifier-only here.
    network_execution_id: Mapped[UUID | None] = mapped_column(nullable=True)
    network_invocation_id: Mapped[UUID | None] = mapped_column(nullable=True)
    parent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_runs.id"),
        nullable=True,
    )
    rerun_of_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_runs.id"),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
