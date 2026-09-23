"""Persist immutable Session-scoped External Context snapshots.

Revision ID: 0071
Revises: 0070
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("external_context_snapshot", postgresql.JSONB(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "network_sessions",
        sa.Column("external_context_snapshot", postgresql.JSONB(), nullable=True),
        schema="network",
    )


def downgrade() -> None:
    op.drop_column(
        "network_sessions",
        "external_context_snapshot",
        schema="network",
    )
    op.drop_column(
        "sessions",
        "external_context_snapshot",
        schema="agent",
    )
