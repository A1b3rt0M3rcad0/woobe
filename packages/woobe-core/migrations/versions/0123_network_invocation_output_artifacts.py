"""Persist Artifact receipts on Network invocations.

Revision ID: 0123
Revises: 0122
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0123"
down_revision = "0122"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "network_invocations",
        sa.Column(
            "output_artifacts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        schema="network",
    )


def downgrade():
    op.drop_column("network_invocations", "output_artifacts", schema="network")
