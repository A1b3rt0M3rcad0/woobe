"""create agent outbox events table

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS agent")
    op.create_table(
        "agent_outbox_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", UUID, nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("event_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("routing_key", sa.String(255), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("causation_id", UUID, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_outbox_idempotency_key"),
        schema="agent",
        comment="Outbox events for the agent bounded context. Owned by module agent.",
    )
    op.create_index(
        "ix_agent_outbox_pending",
        "agent_outbox_events",
        ["status", "available_at", "created_at"],
        schema="agent",
        postgresql_where=sa.text("status IN ('pending', 'retryable')"),
    )
    op.create_index(
        "ix_agent_outbox_correlation_id",
        "agent_outbox_events",
        ["correlation_id"],
        schema="agent",
    )
    op.create_index(
        "ix_agent_outbox_aggregate",
        "agent_outbox_events",
        ["aggregate_type", "aggregate_id"],
        schema="agent",
    )


def downgrade() -> None:
    op.drop_index("ix_agent_outbox_aggregate", table_name="agent_outbox_events", schema="agent")
    op.drop_index("ix_agent_outbox_correlation_id", table_name="agent_outbox_events", schema="agent")
    op.drop_index("ix_agent_outbox_pending", table_name="agent_outbox_events", schema="agent")
    op.drop_table("agent_outbox_events", schema="agent")
