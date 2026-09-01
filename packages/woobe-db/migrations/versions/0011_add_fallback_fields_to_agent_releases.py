"""add fallback fields to agent_releases for snapshot support

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_releases", sa.Column("fallback_provider", sa.String(64), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("fallback_model", sa.String(255), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("fallback_credential_id", sa.Uuid(), nullable=True), schema="ai")
    op.create_foreign_key(
        "fk_agent_releases_fallback_credential",
        "agent_releases",
        "provider_credentials",
        ["fallback_credential_id"],
        ["id"],
        source_schema="ai",
        referent_schema="ai",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agent_releases_fallback_credential", "agent_releases", schema="ai")
    op.drop_column("agent_releases", "fallback_credential_id", schema="ai")
    op.drop_column("agent_releases", "fallback_model", schema="ai")
    op.drop_column("agent_releases", "fallback_provider", schema="ai")
