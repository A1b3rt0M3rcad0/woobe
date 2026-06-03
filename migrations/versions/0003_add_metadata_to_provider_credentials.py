"""add metadata column to provider_credentials

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_credentials",
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        schema="ai",
    )


def downgrade() -> None:
    op.drop_column("provider_credentials", "metadata", schema="ai")
