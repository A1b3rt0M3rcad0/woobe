"""add ask_jobs table for async agent execution

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ask_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("project_id", UUID, sa.ForeignKey("core.projects.id"), nullable=False),
        sa.Column("agent_id", UUID, sa.ForeignKey("ai.agents.id"), nullable=False),
        sa.Column("session_id", UUID, sa.ForeignKey("runtime.sessions.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("params", JSONB, nullable=False),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("trace_id", UUID, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="runtime",
    )
    op.create_index("ix_ask_jobs_status_created", "ask_jobs", ["status", "created_at"], schema="runtime")


def downgrade() -> None:
    op.drop_table("ask_jobs", schema="runtime")
