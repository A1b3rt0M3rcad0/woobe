"""agent release lifecycle indexes

Revision ID: 0031_agent_release_lifecycle
Revises: 0030
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_agent_release_lifecycle"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_agent_releases_draft",
        "agent_releases",
        ["agent_id"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_agent_releases_staging",
        "agent_releases",
        ["agent_id"],
        unique=True,
        schema="agent",
        postgresql_where=sa.text("status = 'staging'"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_releases_staging", table_name="agent_releases", schema="agent")
    op.drop_index("uq_agent_releases_draft", table_name="agent_releases", schema="agent")
