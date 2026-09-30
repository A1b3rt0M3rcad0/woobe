"""Freeze normalized ModelSpec semantics on Agent releases.

Revision ID: 0073
Revises: 0072
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_releases",
        sa.Column("model_spec_snapshot", postgresql.JSONB(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "agent_releases",
        sa.Column("model_spec_hash", sa.String(length=64), nullable=True),
        schema="agent",
    )
    op.add_column(
        "agent_releases",
        sa.Column("fallback_model_spec_snapshot", postgresql.JSONB(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "agent_releases",
        sa.Column("fallback_model_spec_hash", sa.String(length=64), nullable=True),
        schema="agent",
    )


def downgrade() -> None:
    op.drop_column("agent_releases", "fallback_model_spec_hash", schema="agent")
    op.drop_column("agent_releases", "fallback_model_spec_snapshot", schema="agent")
    op.drop_column("agent_releases", "model_spec_hash", schema="agent")
    op.drop_column("agent_releases", "model_spec_snapshot", schema="agent")
