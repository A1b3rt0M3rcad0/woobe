"""Add storage version and journal projection cursors to Agent and Network Runs.

Revision ID: 0066
Revises: 0065
"""

from alembic import op
import sqlalchemy as sa

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "storage_version",
            sa.String(length=32),
            nullable=False,
            server_default="legacy_v1",
        ),
        schema="agent",
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "journal_projected_sequence",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        schema="agent",
    )
    op.add_column(
        "network_executions",
        sa.Column(
            "storage_version",
            sa.String(length=32),
            nullable=False,
            server_default="legacy_v1",
        ),
        schema="network",
    )
    op.add_column(
        "network_executions",
        sa.Column(
            "journal_projected_sequence",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        schema="network",
    )


def downgrade() -> None:
    op.drop_column("network_executions", "journal_projected_sequence", schema="network")
    op.drop_column("network_executions", "storage_version", schema="network")
    op.drop_column("agent_runs", "journal_projected_sequence", schema="agent")
    op.drop_column("agent_runs", "storage_version", schema="agent")
