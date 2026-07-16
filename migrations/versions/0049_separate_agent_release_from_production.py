"""Separate immutable Agent Releases from Playground Production activation.

Revision ID: 0049
Revises: 0048
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE agent.agent_releases
        SET status = 'released', updated_at = now()
        WHERE snapshot_kind = 'release'
          AND status IN ('archived', 'rolled_back')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE agent.agent_releases
        SET status = 'archived', updated_at = now()
        WHERE snapshot_kind = 'release'
          AND status = 'released'
        """
    )
