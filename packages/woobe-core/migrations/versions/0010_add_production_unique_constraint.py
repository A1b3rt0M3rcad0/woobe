"""add partial unique constraint for production status on agent_releases

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_agent_releases_production",
        "agent_releases",
        ["agent_id"],
        unique=True,
        postgresql_where=sa.text("status = 'production'"),
        schema="ai",
    )


def downgrade() -> None:
    op.drop_index(
        "uq_agent_releases_production",
        table_name="agent_releases",
        schema="ai",
        postgresql_where=sa.text("status = 'production'"),
    )
