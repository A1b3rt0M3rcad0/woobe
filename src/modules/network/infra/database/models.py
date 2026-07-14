from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.infra.database.base import BaseModel
from shared.infra.database.inbox import InboxEventModel as BaseInboxEventModel
from shared.infra.database.outbox import OutboxEventModel as BaseOutboxEventModel


class NetworkModel(BaseModel):
    __tablename__ = "networks"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_networks_project_id"),
        {"schema": "network"},
    )

    project_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    draft_definition: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    draft_revision: Mapped[int] = mapped_column(Integer, default=0)
    staging_version_id: Mapped[UUID | None]
    production_version_id: Mapped[UUID | None]


class NetworkVersionModel(BaseModel):
    __tablename__ = "network_versions"
    __table_args__ = (
        UniqueConstraint("network_id", "version", name="uq_network_versions_version"),
        Index("ix_network_versions_project_kind", "project_id", "kind", "created_at"),
        {"schema": "network"},
    )

    network_id: Mapped[UUID] = mapped_column(ForeignKey("network.networks.id"))
    project_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(64))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    resolved_bindings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    composition_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[UUID | None]
    rollback_of_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network.network_versions.id")
    )


class NetworkSessionModel(BaseModel):
    __tablename__ = "network_sessions"
    __table_args__ = (
        Index(
            "ix_network_sessions_network_environment",
            "network_id",
            "environment",
            "created_at",
        ),
        Index(
            "ix_network_sessions_project_status", "project_id", "status", "created_at"
        ),
        UniqueConstraint(
            "network_id",
            "external_session_id",
            name="uq_network_sessions_external_id",
        ),
        CheckConstraint(
            "(environment = 'draft' AND network_version_id IS NULL) OR "
            "(environment IN ('staging', 'production') AND network_version_id IS NOT NULL)",
            name="ck_network_sessions_environment_version",
        ),
        {"schema": "network"},
    )

    network_id: Mapped[UUID] = mapped_column(ForeignKey("network.networks.id"))
    network_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network.network_versions.id"), nullable=True
    )
    project_id: Mapped[UUID]
    environment: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="New Network session")
    tenant_id: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[str | None] = mapped_column(String(128))
    external_session_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkMessageModel(BaseModel):
    __tablename__ = "network_messages"
    __table_args__ = (
        Index(
            "ix_network_messages_session_created", "network_session_id", "created_at"
        ),
        {"schema": "network"},
    )

    network_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("network.network_sessions.id")
    )
    network_execution_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network.network_executions.id")
    )
    project_id: Mapped[UUID]
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class NetworkAgentContextModel(BaseModel):
    __tablename__ = "network_agent_contexts"
    __table_args__ = (
        UniqueConstraint(
            "network_session_id",
            "network_node_id",
            name="uq_network_agent_context_session_node",
        ),
        Index("ix_network_agent_contexts_agent_session", "agent_session_id"),
        {"schema": "network"},
    )

    network_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("network.network_sessions.id")
    )
    network_node_id: Mapped[UUID]
    agent_id: Mapped[UUID]
    agent_session_id: Mapped[UUID | None]


class NetworkExecutionModel(BaseModel):
    __tablename__ = "network_executions"
    __table_args__ = (
        Index("ix_network_executions_status_created", "status", "created_at"),
        Index(
            "ix_network_executions_project_status", "project_id", "status", "created_at"
        ),
        Index("ix_network_executions_lease", "status", "lease_expires_at"),
        Index(
            "uq_network_execution_active_session",
            "network_session_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'running', 'cancel_requested')"
            ),
        ),
        UniqueConstraint(
            "network_id",
            "idempotency_key",
            name="uq_network_execution_idempotency",
        ),
        CheckConstraint(
            "(network_version_id IS NULL AND draft_revision IS NOT NULL "
            "AND definition_snapshot IS NOT NULL "
            "AND resolved_bindings_snapshot IS NOT NULL) OR "
            "(network_version_id IS NOT NULL AND draft_revision IS NULL)",
            name="ck_network_executions_snapshot_source",
        ),
        Index(
            "ix_network_executions_network_draft_revision",
            "network_id",
            "draft_revision",
            "created_at",
        ),
        {"schema": "network"},
    )

    network_id: Mapped[UUID] = mapped_column(ForeignKey("network.networks.id"))
    network_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network.network_versions.id"), nullable=True
    )
    network_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("network.network_sessions.id")
    )
    project_id: Mapped[UUID]
    input_message: Mapped[str] = mapped_column(Text)
    draft_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    definition_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    resolved_bindings_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    output_message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    root_trace_id: Mapped[UUID | None]
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_generation: Mapped[int] = mapped_column(Integer, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_detail: Mapped[str | None] = mapped_column(Text)
    last_event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkInvocationModel(BaseModel):
    __tablename__ = "network_invocations"
    __table_args__ = (
        Index(
            "ix_network_invocations_execution_created",
            "network_execution_id",
            "created_at",
        ),
        Index("ix_network_invocations_parent", "parent_invocation_id"),
        {"schema": "network"},
    )

    network_execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("network.network_executions.id")
    )
    network_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("network.network_sessions.id")
    )
    parent_invocation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("network.network_invocations.id")
    )
    node_id: Mapped[UUID]
    agent_id: Mapped[UUID]
    agent_session_id: Mapped[UUID | None]
    trace_id: Mapped[UUID | None]
    depth: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    input_message: Mapped[str] = mapped_column(Text)
    output_message: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)


class NetworkExecutionEventModel(BaseModel):
    __tablename__ = "network_execution_events"
    __table_args__ = (
        UniqueConstraint(
            "network_execution_id",
            "sequence",
            name="uq_network_execution_event_sequence",
        ),
        Index(
            "ix_network_execution_events_execution_created",
            "network_execution_id",
            "created_at",
        ),
        {"schema": "network"},
    )

    network_execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("network.network_executions.id")
    )
    network_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("network.network_sessions.id")
    )
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    invocation_id: Mapped[UUID | None]
    parent_invocation_id: Mapped[UUID | None]
    node_id: Mapped[UUID | None]
    agent_id: Mapped[UUID | None]
    depth: Mapped[int | None]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class NetworkOutboxEventModel(BaseOutboxEventModel):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_network_outbox_idempotency"),
        Index(
            "ix_network_outbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('pending', 'retryable')"),
        ),
        {"schema": "network"},
    )


class NetworkInboxEventModel(BaseInboxEventModel):
    __tablename__ = "inbox_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_network_inbox_message_id"),
        UniqueConstraint("idempotency_key", name="uq_network_inbox_idempotency"),
        Index(
            "ix_network_inbox_pending",
            "status",
            "available_at",
            "created_at",
            postgresql_where=text("status IN ('received', 'retryable')"),
        ),
        {"schema": "network"},
    )
