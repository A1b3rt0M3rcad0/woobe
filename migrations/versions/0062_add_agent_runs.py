"""add canonical Agent Runs

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("input_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("output_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_message", sa.Text(), nullable=False),
        sa.Column("execution_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("network_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("network_invocation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rerun_of_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled', 'uncertain')",
            name="ck_agent_runs_status",
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.agents.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["agent.sessions.id"]),
        sa.ForeignKeyConstraint(["agent_release_id"], ["agent.agent_releases.id"]),
        sa.ForeignKeyConstraint(["input_message_id"], ["agent.messages.id"]),
        sa.ForeignKeyConstraint(["output_message_id"], ["agent.messages.id"]),
        sa.ForeignKeyConstraint(["parent_run_id"], ["agent.agent_runs.id"]),
        sa.ForeignKeyConstraint(["rerun_of_run_id"], ["agent.agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="agent",
    )
    op.create_index("ix_agent_runs_project_status_created", "agent_runs", ["project_id", "status", "created_at"], schema="agent")
    op.create_index("ix_agent_runs_agent_created", "agent_runs", ["agent_id", "created_at"], schema="agent")
    op.create_index("ix_agent_runs_session_created", "agent_runs", ["session_id", "created_at"], schema="agent")
    op.create_index("ix_agent_runs_network_execution", "agent_runs", ["network_execution_id", "created_at"], schema="agent")
    op.create_index("ix_agent_runs_trace", "agent_runs", ["trace_id"], schema="agent")


def downgrade() -> None:
    op.drop_index("ix_agent_runs_trace", table_name="agent_runs", schema="agent")
    op.drop_index("ix_agent_runs_network_execution", table_name="agent_runs", schema="agent")
    op.drop_index("ix_agent_runs_session_created", table_name="agent_runs", schema="agent")
    op.drop_index("ix_agent_runs_agent_created", table_name="agent_runs", schema="agent")
    op.drop_index("ix_agent_runs_project_status_created", table_name="agent_runs", schema="agent")
    op.drop_table("agent_runs", schema="agent")
