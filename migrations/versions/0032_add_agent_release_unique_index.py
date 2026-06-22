"""add agent release unique index

Revision ID: 0032_add_agent_release_unique_index
Revises: 0031_agent_release_lifecycle
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_add_agent_release_unique_index"
down_revision = "0031_agent_release_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_agent_releases_production",
        "agent_releases",
        ["agent_id"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status = 'production'"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_releases_production", table_name="agent_releases", schema="agent")
