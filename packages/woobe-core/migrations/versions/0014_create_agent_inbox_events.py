"""create agent inbox events table

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS agent")
    op.create_table(
        "agent_inbox_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("message_id", sa.String(255), nullable=False),
        sa.Column("producer_module", sa.String(64), nullable=False),
        sa.Column("consumer_module", sa.String(64), nullable=False, server_default="agent"),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("event_version", sa.Integer, nullable=False),
        sa.Column("routing_key", sa.String(255), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("headers", JSONB, nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("correlation_id", UUID, nullable=False),
        sa.Column("causation_id", UUID, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(128), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("message_id", name="uq_agent_inbox_message_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_inbox_idempotency_key"),
        schema="agent",
        comment="Inbox events for the agent bounded context. Owned by module agent.",
    )
    op.create_index(
        "ix_agent_inbox_pending",
        "agent_inbox_events",
        ["status", "available_at", "created_at"],
        schema="agent",
        postgresql_where=sa.text("status IN ('received', 'retryable')"),
    )
    op.create_index(
        "ix_agent_inbox_correlation_id",
        "agent_inbox_events",
        ["correlation_id"],
        schema="agent",
    )


def downgrade() -> None:
    op.drop_index("ix_agent_inbox_correlation_id", table_name="agent_inbox_events", schema="agent")
    op.drop_index("ix_agent_inbox_pending", table_name="agent_inbox_events", schema="agent")
    op.drop_table("agent_inbox_events", schema="agent")
