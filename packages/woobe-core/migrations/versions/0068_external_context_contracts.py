"""Add External Context contracts to Agent and Network Release snapshots.

Revision ID: 0068
Revises: 0067
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0068"
down_revision = "0067"
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
    op.add_column(
        "agent_releases",
        sa.Column("external_context_contract", postgresql.JSONB(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "network_versions",
        sa.Column(
            "effective_external_context_contract",
            postgresql.JSONB(),
            nullable=True,
        ),
        schema="network",
    )
    op.add_column(
        "network_sessions",
        sa.Column(
            "external_context_session_values",
            postgresql.JSONB(),
            nullable=True,
        ),
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column("external_context_snapshot", postgresql.JSONB(), nullable=True),
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
    op.drop_column(
        "network_executions",
        "external_context_snapshot",
        schema="network",
    )
    op.drop_column(
        "network_sessions",
        "external_context_session_values",
        schema="network",
    )
    op.drop_column(
        "network_versions",
        "effective_external_context_contract",
        schema="network",
    )
    op.drop_column(
        "agent_releases",
        "external_context_contract",
        schema="agent",
    )
