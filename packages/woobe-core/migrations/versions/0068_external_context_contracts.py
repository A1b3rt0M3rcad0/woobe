"""Add External Context contracts to Agent and Network Release snapshots.

Revision ID: 0068
Revises: 0067
"""

from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_releases",
        postgresql.JSONB().with_variant(postgresql.JSONB(), "postgresql"),
        schema="agent",
    )


def downgrade() -> None:
    pass
