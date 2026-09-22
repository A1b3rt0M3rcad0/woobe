"""Persist External Context test values on runtime environment states.

Revision ID: 0069
Revises: 0068
"""

from alembic import op


revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0068 existed in the feature branch before these columns were introduced.
    # Some developer databases may therefore already contain them even though
    # their Alembic revision is still 0068. IF NOT EXISTS makes the repair
    # safe for both the old-0068 and transient-new-0068 database shapes.
    op.execute(
        """
        ALTER TABLE agent.agent_runtime_environment_states
        ADD COLUMN IF NOT EXISTS external_context_values JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE network.network_runtime_environment_states
        ADD COLUMN IF NOT EXISTS external_context_values JSONB NOT NULL DEFAULT '{}'::jsonb
        """
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
