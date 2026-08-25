"""add Agent release activation audit description

Revision ID: 0054
Revises: 0053
"""

import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_release_activations",
        sa.Column("change_description", sa.Text(), nullable=True),
        schema="agent",
    )


def downgrade() -> None:
    op.drop_column(
        "agent_release_activations",
        "change_description",
        schema="agent",
    )
