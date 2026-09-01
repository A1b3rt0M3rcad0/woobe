"""add mode column to runtime.sessions

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("mode", sa.String(32), nullable=False, server_default="chat"),
        schema="runtime",
    )


def downgrade() -> None:
    op.drop_column("sessions", "mode", schema="runtime")
