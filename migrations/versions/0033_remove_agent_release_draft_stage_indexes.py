"""remove obsolete agent release draft stage indexes

Revision ID: 0033_release_draft_stage_idx
Revises: 0032_release_prod_index_noop
"""

from alembic import op
import sqlalchemy as sa


revision = "0033_release_draft_stage_idx"
down_revision = "0032_release_prod_index_noop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_agent_releases_staging", table_name="agent_releases", schema="agent")
    op.drop_index("uq_agent_releases_draft", table_name="agent_releases", schema="agent")


def downgrade() -> None:
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
