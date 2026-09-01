"""make tool agent_id nullable so tools can exist at project level

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "tools",
        "agent_id",
        existing_type=sa.Uuid(),
        nullable=True,
        schema="tools",
    )


def downgrade() -> None:
    op.alter_column(
        "tools",
        "agent_id",
        existing_type=sa.Uuid(),
        nullable=False,
        schema="tools",
    )
