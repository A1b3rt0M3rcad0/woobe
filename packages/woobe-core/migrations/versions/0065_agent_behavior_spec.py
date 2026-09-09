"""Add structured Behavior without rewriting historical instructions.

Revision ID: 0065
Revises: 0064
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("agents", "agent_releases"):
        op.add_column(
            table,
            sa.Column("behavior_spec", postgresql.JSONB(none_as_null=True), nullable=True),
            schema="agent",
        )


def downgrade() -> None:
    for table in ("agent_releases", "agents"):
        op.drop_column(table, "behavior_spec", schema="agent")
