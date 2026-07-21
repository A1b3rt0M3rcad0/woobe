"""add evaluator suite authoring and outcome contracts

Revision ID: 0057
Revises: 0056
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dataset_versions",
        sa.Column("authoring_source", sa.String(length=32), nullable=False, server_default="manual"),
        schema="evaluation",
    )
    op.add_column(
        "dataset_versions",
        sa.Column("source_snapshot_hash", sa.String(length=64), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "dataset_versions",
        sa.Column("source_context_hash", sa.String(length=64), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "dataset_versions",
        sa.Column("authoring_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "dataset_versions",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "dataset_versions",
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_dataset_versions_source_snapshot",
        "dataset_versions",
        ["project_id", "source_snapshot_hash"],
        schema="evaluation",
    )

    op.add_column(
        "test_cases",
        sa.Column("case_type", sa.String(length=32), nullable=False, server_default="success"),
        schema="evaluation",
    )
    op.create_check_constraint(
        "ck_evaluation_test_cases_case_type",
        "test_cases",
        "case_type IN ('success', 'refusal', 'handled_error', 'expected_failure')",
        schema="evaluation",
    )

    op.add_column(
        "trials",
        sa.Column("observed_outcome", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "trials",
        sa.Column("failure_origin", sa.String(length=32), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "trials",
        sa.Column("failure_stage", sa.String(length=32), nullable=True),
        schema="evaluation",
    )

    op.create_table(
        "authoring_calls",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_entity_id", sa.Uuid(), nullable=False),
        sa.Column("target_source_type", sa.String(length=32), nullable=False),
        sa.Column("target_version_id", sa.Uuid(), nullable=True),
        sa.Column("target_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("generator_provider_model_id", sa.Uuid(), nullable=False),
        sa.Column("generator_provider_credential_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("requested_case_count", sa.Integer(), nullable=False),
        sa.Column("coverage_request", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False, server_default="suite-generator-v1"),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("context_stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=18, scale=10), nullable=True),
        sa.Column("pricing_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "requested_case_count BETWEEN 1 AND 100",
            name="ck_evaluation_authoring_case_count",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_calls_project_created",
        "authoring_calls",
        ["project_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_calls_snapshot",
        "authoring_calls",
        ["project_id", "target_snapshot_hash"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_calls_status",
        "authoring_calls",
        ["status", "created_at"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_authoring_calls_status",
        table_name="authoring_calls",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_authoring_calls_snapshot",
        table_name="authoring_calls",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_authoring_calls_project_created",
        table_name="authoring_calls",
        schema="evaluation",
    )
    op.drop_table("authoring_calls", schema="evaluation")

    op.drop_column("trials", "failure_stage", schema="evaluation")
    op.drop_column("trials", "failure_origin", schema="evaluation")
    op.drop_column("trials", "observed_outcome", schema="evaluation")

    op.drop_constraint(
        "ck_evaluation_test_cases_case_type",
        "test_cases",
        type_="check",
        schema="evaluation",
    )
    op.drop_column("test_cases", "case_type", schema="evaluation")

    op.drop_index(
        "ix_evaluation_dataset_versions_source_snapshot",
        table_name="dataset_versions",
        schema="evaluation",
    )
    op.drop_column("dataset_versions", "reviewed_by", schema="evaluation")
    op.drop_column("dataset_versions", "reviewed_at", schema="evaluation")
    op.drop_column("dataset_versions", "authoring_metadata", schema="evaluation")
    op.drop_column("dataset_versions", "source_context_hash", schema="evaluation")
    op.drop_column("dataset_versions", "source_snapshot_hash", schema="evaluation")
    op.drop_column("dataset_versions", "authoring_source", schema="evaluation")
