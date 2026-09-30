"""Add normalized ModelSpec fields to ProviderModel.

Revision ID: 0072
Revises: 0071
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "provider_models",
        sa.Column("model_type", sa.String(length=64), nullable=True),
        schema="agent",
    )
    op.add_column(
        "provider_models",
        sa.Column("spec", postgresql.JSONB(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "provider_models",
        sa.Column("spec_version", sa.Integer(), nullable=True),
        schema="agent",
    )
    op.add_column(
        "provider_models",
        sa.Column("spec_hash", sa.String(length=64), nullable=True),
        schema="agent",
    )


def downgrade() -> None:
    op.drop_column("provider_models", "spec_hash", schema="agent")
    op.drop_column("provider_models", "spec_version", schema="agent")
    op.drop_column("provider_models", "spec", schema="agent")
    op.drop_column("provider_models", "model_type", schema="agent")
