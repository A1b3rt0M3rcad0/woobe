"""Create durable Network runtime.

Revision ID: 0042
Revises: 0041
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _messaging_columns() -> list[sa.Column]:
    return [
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("event_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("routing_key", sa.String(255), nullable=False),
        sa.Column(
            "payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("correlation_id", UUID, nullable=True),
        sa.Column("causation_id", UUID, nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS network")

    op.create_table(
        "networks",
        *_base_columns(),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "draft_definition",
            JSONB,
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("draft_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("staging_version_id", UUID, nullable=True),
        sa.Column("production_version_id", UUID, nullable=True),
        sa.UniqueConstraint("project_id", name="uq_networks_project_id"),
        schema="network",
    )

    op.create_table(
        "network_versions",
        *_base_columns(),
        sa.Column("network_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("resolved_bindings", JSONB, nullable=False),
        sa.Column("composition_hash", sa.String(64), nullable=False),
        sa.Column("created_by", UUID, nullable=True),
        sa.Column("rollback_of_version_id", UUID, nullable=True),
        sa.ForeignKeyConstraint(["network_id"], ["network.networks.id"]),
        sa.ForeignKeyConstraint(
            ["rollback_of_version_id"], ["network.network_versions.id"]
        ),
        sa.UniqueConstraint(
            "network_id", "version", name="uq_network_versions_version"
        ),
        schema="network",
    )
    op.create_index(
        "ix_network_versions_project_kind",
        "network_versions",
        ["project_id", "kind", "created_at"],
        schema="network",
    )

    op.create_table(
        "network_sessions",
        *_base_columns(),
        sa.Column("network_id", UUID, nullable=False),
        sa.Column("network_version_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("external_session_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["network_id"], ["network.networks.id"]),
        sa.ForeignKeyConstraint(
            ["network_version_id"], ["network.network_versions.id"]
        ),
        sa.UniqueConstraint(
            "network_id",
            "external_session_id",
            name="uq_network_sessions_external_id",
        ),
        schema="network",
    )
    op.create_index(
        "ix_network_sessions_network_environment",
        "network_sessions",
        ["network_id", "environment", "created_at"],
        schema="network",
    )
    op.create_index(
        "ix_network_sessions_project_status",
        "network_sessions",
        ["project_id", "status", "created_at"],
        schema="network",
    )

    op.create_table(
        "network_executions",
        *_base_columns(),
        sa.Column("network_id", UUID, nullable=False),
        sa.Column("network_version_id", UUID, nullable=False),
        sa.Column("network_session_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("input_message", sa.Text(), nullable=False),
        sa.Column("output_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), server_default="queued", nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("root_trace_id", UUID, nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column(
            "last_event_sequence", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["network_id"], ["network.networks.id"]),
        sa.ForeignKeyConstraint(
            ["network_version_id"], ["network.network_versions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["network_session_id"], ["network.network_sessions.id"]
        ),
        sa.UniqueConstraint(
            "network_id",
            "idempotency_key",
            name="uq_network_execution_idempotency",
        ),
        schema="network",
    )
    op.create_index(
        "ix_network_executions_status_created",
        "network_executions",
        ["status", "created_at"],
        schema="network",
    )
    op.create_index(
        "ix_network_executions_project_status",
        "network_executions",
        ["project_id", "status", "created_at"],
        schema="network",
    )
    op.create_index(
        "ix_network_executions_lease",
        "network_executions",
        ["status", "lease_expires_at"],
        schema="network",
    )
    op.create_index(
        "uq_network_execution_active_session",
        "network_executions",
        ["network_session_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'cancel_requested')"),
        schema="network",
    )

    op.create_table(
        "network_messages",
        *_base_columns(),
        sa.Column("network_session_id", UUID, nullable=False),
        sa.Column("network_execution_id", UUID, nullable=True),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data", JSONB, nullable=True),
        sa.ForeignKeyConstraint(
            ["network_session_id"], ["network.network_sessions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["network_execution_id"], ["network.network_executions.id"]
        ),
        schema="network",
    )
    op.create_index(
        "ix_network_messages_session_created",
        "network_messages",
        ["network_session_id", "created_at"],
        schema="network",
    )

    op.create_table(
        "network_agent_contexts",
        *_base_columns(),
        sa.Column("network_session_id", UUID, nullable=False),
        sa.Column("network_node_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        sa.Column("agent_session_id", UUID, nullable=True),
        sa.ForeignKeyConstraint(
            ["network_session_id"], ["network.network_sessions.id"]
        ),
        sa.UniqueConstraint(
            "network_session_id",
            "network_node_id",
            name="uq_network_agent_context_session_node",
        ),
        schema="network",
    )
    op.create_index(
        "ix_network_agent_contexts_agent_session",
        "network_agent_contexts",
        ["agent_session_id"],
        schema="network",
    )

    op.create_table(
        "network_invocations",
        *_base_columns(),
        sa.Column("network_execution_id", UUID, nullable=False),
        sa.Column("network_session_id", UUID, nullable=False),
        sa.Column("parent_invocation_id", UUID, nullable=True),
        sa.Column("node_id", UUID, nullable=False),
        sa.Column("agent_id", UUID, nullable=False),
        sa.Column("agent_session_id", UUID, nullable=True),
        sa.Column("trace_id", UUID, nullable=True),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("input_message", sa.Text(), nullable=False),
        sa.Column("output_message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["network_execution_id"], ["network.network_executions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["network_session_id"], ["network.network_sessions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["parent_invocation_id"], ["network.network_invocations.id"]
        ),
        schema="network",
    )
    op.create_index(
        "ix_network_invocations_execution_created",
        "network_invocations",
        ["network_execution_id", "created_at"],
        schema="network",
    )
    op.create_index(
        "ix_network_invocations_parent",
        "network_invocations",
        ["parent_invocation_id"],
        schema="network",
    )

    op.create_table(
        "network_execution_events",
        *_base_columns(),
        sa.Column("network_execution_id", UUID, nullable=False),
        sa.Column("network_session_id", UUID, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("invocation_id", UUID, nullable=True),
        sa.Column("parent_invocation_id", UUID, nullable=True),
        sa.Column("node_id", UUID, nullable=True),
        sa.Column("agent_id", UUID, nullable=True),
        sa.Column("depth", sa.Integer(), nullable=True),
        sa.Column(
            "payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["network_execution_id"], ["network.network_executions.id"]
        ),
        sa.ForeignKeyConstraint(
            ["network_session_id"], ["network.network_sessions.id"]
        ),
        sa.UniqueConstraint(
            "network_execution_id",
            "sequence",
            name="uq_network_execution_event_sequence",
        ),
        schema="network",
    )
    op.create_index(
        "ix_network_execution_events_execution_created",
        "network_execution_events",
        ["network_execution_id", "created_at"],
        schema="network",
    )

    op.create_table(
        "outbox_events",
        *_base_columns(),
        *_messaging_columns(),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_network_outbox_idempotency"),
        schema="network",
    )
    op.create_index(
        "ix_network_outbox_pending",
        "outbox_events",
        ["status", "available_at", "created_at"],
        postgresql_where=sa.text("status IN ('pending', 'retryable')"),
        schema="network",
    )

    op.create_table(
        "inbox_events",
        *_base_columns(),
        *_messaging_columns(),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("producer_module", sa.String(64), nullable=False),
        sa.Column("consumer_module", sa.String(64), nullable=False),
        sa.Column("outbox_origin_id", UUID, nullable=True),
        sa.Column("headers", JSONB, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumer_name", sa.String(128), nullable=True),
        sa.UniqueConstraint("message_id", name="uq_network_inbox_message_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_network_inbox_idempotency"),
        schema="network",
    )
    op.create_index(
        "ix_network_inbox_pending",
        "inbox_events",
        ["status", "available_at", "created_at"],
        postgresql_where=sa.text("status IN ('received', 'retryable')"),
        schema="network",
    )


def downgrade() -> None:
    for table in [
        "inbox_events",
        "outbox_events",
        "network_execution_events",
        "network_invocations",
        "network_agent_contexts",
        "network_messages",
        "network_executions",
        "network_sessions",
        "network_versions",
        "networks",
    ]:
        op.drop_table(table, schema="network")
    op.execute("DROP SCHEMA IF EXISTS network")
