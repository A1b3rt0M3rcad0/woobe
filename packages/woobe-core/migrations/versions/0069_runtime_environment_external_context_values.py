"""Persist External Context test values on runtime environment states.

Revision ID: 0069
Revises: 0068
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_runtime_environment_states",
        sa.Column(
            "external_context_values",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="agent",
    )
    op.add_column(
        "network_runtime_environment_states",
        sa.Column(
            "external_context_values",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="network",
    )


def downgrade() -> None:
    op.drop_column(
        "network_runtime_environment_states",
        "external_context_values",
        schema="network",
    )
    op.drop_column(
        "agent_runtime_environment_states",
        "external_context_values",
        schema="agent",
    )
