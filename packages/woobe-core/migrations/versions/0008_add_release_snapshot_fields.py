"""add snapshot fields to agent_releases for complete agent config per release

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_releases", sa.Column("system_prompt", sa.Text(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("output_schema", postgresql.JSONB(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("provider", sa.String(64), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("model", sa.String(255), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("provider_credential_id", sa.Uuid(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("temperature", sa.Float(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("max_output_tokens", sa.Integer(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("session_mode", sa.String(32), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("collection_ids", postgresql.ARRAY(sa.Uuid()), nullable=True), schema="ai")

    op.create_foreign_key(
        "fk_agent_releases_provider_credential",
        "agent_releases", "provider_credentials",
        ["provider_credential_id"], ["id"],
        source_schema="ai", referent_schema="ai",
    )


def downgrade() -> None:
    op.drop_constraint("fk_agent_releases_provider_credential", "agent_releases", schema="ai")
    op.drop_column("agent_releases", "collection_ids", schema="ai")
    op.drop_column("agent_releases", "session_mode", schema="ai")
    op.drop_column("agent_releases", "max_output_tokens", schema="ai")
    op.drop_column("agent_releases", "temperature", schema="ai")
    op.drop_column("agent_releases", "provider_credential_id", schema="ai")
    op.drop_column("agent_releases", "model", schema="ai")
    op.drop_column("agent_releases", "provider", schema="ai")
    op.drop_column("agent_releases", "output_schema", schema="ai")
    op.drop_column("agent_releases", "system_prompt", schema="ai")
