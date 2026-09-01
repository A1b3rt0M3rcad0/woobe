"""add context engineering core

Revision ID: 0063
Revises: 0062
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_invocations",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.Uuid(), nullable=True),
        sa.Column("network_execution_id", sa.Uuid(), nullable=True),
        sa.Column("network_invocation_id", sa.Uuid(), nullable=True),
        sa.Column("call_index", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=96), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("provider_model_id", sa.Uuid(), nullable=True),
        sa.Column("provider_credential_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_units", sa.BigInteger(), nullable=True),
        sa.Column("output_units", sa.BigInteger(), nullable=True),
        sa.Column("total_units", sa.BigInteger(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("usage_complete", sa.Boolean(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent.agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="agent",
    )
    op.create_index("ix_agent_model_invocations_run_call", "model_invocations", ["agent_run_id", "call_index"], schema="agent")
    op.create_index("ix_agent_model_invocations_project_created", "model_invocations", ["project_id", "created_at"], schema="agent")
    op.create_index("ix_agent_model_invocations_trace", "model_invocations", ["trace_id"], schema="agent")
    op.create_index("ix_agent_model_invocations_network_execution", "model_invocations", ["network_execution_id", "created_at"], schema="agent")

    op.create_table(
        "context_snapshots",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("model_invocation_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False),
        sa.Column("policy_schema_version", sa.Integer(), nullable=False),
        sa.Column("policy_hash", sa.String(length=64), nullable=False),
        sa.Column("model_capacity_units", sa.BigInteger(), nullable=True),
        sa.Column("reserved_output_units", sa.BigInteger(), nullable=True),
        sa.Column("runtime_reserve_units", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("usable_input_budget", sa.BigInteger(), nullable=True),
        sa.Column("estimated_input_units", sa.BigInteger(), nullable=False),
        sa.Column("reported_input_units", sa.BigInteger(), nullable=True),
        sa.Column("utilization", sa.Float(), nullable=True),
        sa.Column("pressure_status", sa.String(length=32), nullable=False),
        sa.Column("measurement_status", sa.String(length=32), nullable=False),
        sa.Column("manifest", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("materialized_hash", sa.String(length=64), nullable=False),
        sa.Column("retention_mode", sa.String(length=32), nullable=False),
        sa.Column("reproduction_level", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["model_invocation_id"], ["agent.model_invocations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent.agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_invocation_id", name="uq_agent_context_snapshot_model_invocation"),
        schema="agent",
    )
    op.create_index("ix_agent_context_snapshots_run_created", "context_snapshots", ["agent_run_id", "created_at"], schema="agent")
    op.create_index("ix_agent_context_snapshots_project_created", "context_snapshots", ["project_id", "created_at"], schema="agent")

    op.create_table(
        "context_contributions",
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.String(length=512), nullable=True),
        sa.Column("parent_ref", sa.String(length=512), nullable=True),
        sa.Column("modality", sa.String(length=32), nullable=False, server_default="text"),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("raw_units", sa.BigInteger(), nullable=True),
        sa.Column("materialized_units", sa.BigInteger(), nullable=True),
        sa.Column("selection_method", sa.String(length=96), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("transformations", postgresql.JSONB(), nullable=True),
        sa.Column("trust", sa.String(length=64), nullable=True),
        sa.Column("sensitivity", sa.String(length=64), nullable=True),
        sa.Column("integrity_hash", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["agent.context_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "ordinal", name="uq_agent_context_contribution_ordinal"),
        schema="agent",
    )
    op.create_index("ix_agent_context_contributions_snapshot", "context_contributions", ["snapshot_id", "ordinal"], schema="agent")
    op.create_index("ix_agent_context_contributions_source", "context_contributions", ["source_type", "source_ref"], schema="agent")


def downgrade() -> None:
    op.drop_index("ix_agent_context_contributions_source", table_name="context_contributions", schema="agent")
    op.drop_index("ix_agent_context_contributions_snapshot", table_name="context_contributions", schema="agent")
    op.drop_table("context_contributions", schema="agent")
    op.drop_index("ix_agent_context_snapshots_project_created", table_name="context_snapshots", schema="agent")
    op.drop_index("ix_agent_context_snapshots_run_created", table_name="context_snapshots", schema="agent")
    op.drop_table("context_snapshots", schema="agent")
    op.drop_index("ix_agent_model_invocations_network_execution", table_name="model_invocations", schema="agent")
    op.drop_index("ix_agent_model_invocations_trace", table_name="model_invocations", schema="agent")
    op.drop_index("ix_agent_model_invocations_project_created", table_name="model_invocations", schema="agent")
    op.drop_index("ix_agent_model_invocations_run_call", table_name="model_invocations", schema="agent")
    op.drop_table("model_invocations", schema="agent")
