"""add name, description, response_format, base_url, runtime_config, agent_status to agent_releases

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_releases", sa.Column("name", sa.String(255), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("description", sa.Text(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("response_format", postgresql.JSONB(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("base_url", sa.String(512), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("runtime_config", postgresql.JSONB(), nullable=True), schema="ai")
    op.add_column("agent_releases", sa.Column("agent_status", sa.String(32), nullable=True), schema="ai")


def downgrade() -> None:
    op.drop_column("agent_releases", "agent_status", schema="ai")
    op.drop_column("agent_releases", "runtime_config", schema="ai")
    op.drop_column("agent_releases", "base_url", schema="ai")
    op.drop_column("agent_releases", "response_format", schema="ai")
    op.drop_column("agent_releases", "description", schema="ai")
    op.drop_column("agent_releases", "name", schema="ai")
