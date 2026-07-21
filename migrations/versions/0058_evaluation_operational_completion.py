"""complete evaluation authoring and operations

Revision ID: 0058
Revises: 0057
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None

UUID = sa.Uuid
JSONB = postgresql.JSONB


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "datasets",
        sa.Column("archived_by", UUID(), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "suites",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "suites",
        sa.Column("archived_by", UUID(), nullable=True),
        schema="evaluation",
    )

    op.add_column(
        "suite_versions",
        sa.Column("parent_version_id", UUID(), nullable=True),
        schema="evaluation",
    )
    op.create_foreign_key(
        "fk_evaluation_suite_versions_parent",
        "suite_versions",
        "suite_versions",
        ["parent_version_id"],
        ["id"],
        source_schema="evaluation",
        referent_schema="evaluation",
    )
    op.add_column(
        "suite_versions",
        sa.Column("change_description", sa.Text(), nullable=True),
        schema="evaluation",
    )

    op.add_column(
        "runs",
        sa.Column(
            "execution_policy",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema="evaluation",
    )

    op.add_column(
        "authoring_calls",
        sa.Column("context_payload", JSONB(), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "authoring_calls",
        sa.Column("total_batch_count", sa.Integer(), nullable=False, server_default="0"),
        schema="evaluation",
    )
    op.add_column(
        "authoring_calls",
        sa.Column("completed_batch_count", sa.Integer(), nullable=False, server_default="0"),
        schema="evaluation",
    )
    op.add_column(
        "authoring_calls",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "authoring_calls",
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "authoring_calls",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )

    op.create_table(
        "authoring_batches",
        sa.Column("id", UUID(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "authoring_call_id",
            UUID(),
            sa.ForeignKey("evaluation.authoring_calls.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("requested_case_count", sa.Integer(), nullable=False),
        sa.Column("coverage_request", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 10), nullable=True),
        sa.Column("pricing_snapshot", JSONB(), nullable=True),
        sa.Column("generated_payload", JSONB(), nullable=True),
        sa.Column("validation_result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "authoring_call_id",
            "batch_index",
            name="uq_evaluation_authoring_batches_index",
        ),
        sa.CheckConstraint(
            "requested_case_count BETWEEN 1 AND 10",
            name="ck_evaluation_authoring_batch_case_count",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_batches_call_status",
        "authoring_batches",
        ["authoring_call_id", "status", "batch_index"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_authoring_batches_project_created",
        "authoring_batches",
        ["project_id", "created_at"],
        schema="evaluation",
    )

    op.add_column(
        "estimate_runs",
        sa.Column("price_snapshot_hash", sa.String(length=64), nullable=False, server_default="none"),
        schema="evaluation",
    )
    op.drop_constraint(
        "uq_evaluation_estimates_run_target",
        "estimate_runs",
        schema="evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_evaluation_estimates_run_target_volume_price",
        "estimate_runs",
        [
            "evaluation_run_id",
            "target_id",
            "volume",
            "volume_unit",
            "price_snapshot_hash",
        ],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_evaluation_estimates_run_target_volume_price",
        "estimate_runs",
        schema="evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_evaluation_estimates_run_target",
        "estimate_runs",
        ["evaluation_run_id", "target_id"],
        schema="evaluation",
    )
    op.drop_column("estimate_runs", "price_snapshot_hash", schema="evaluation")

    op.drop_index(
        "ix_evaluation_authoring_batches_project_created",
        table_name="authoring_batches",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_authoring_batches_call_status",
        table_name="authoring_batches",
        schema="evaluation",
    )
    op.drop_table("authoring_batches", schema="evaluation")

    op.drop_column("authoring_calls", "lease_expires_at", schema="evaluation")
    op.drop_column("authoring_calls", "lease_owner", schema="evaluation")
    op.drop_column("authoring_calls", "cancel_requested_at", schema="evaluation")
    op.drop_column("authoring_calls", "completed_batch_count", schema="evaluation")
    op.drop_column("authoring_calls", "total_batch_count", schema="evaluation")
    op.drop_column("authoring_calls", "context_payload", schema="evaluation")

    op.drop_column("runs", "execution_policy", schema="evaluation")
    op.drop_column("suite_versions", "change_description", schema="evaluation")
    op.drop_constraint(
        "fk_evaluation_suite_versions_parent",
        "suite_versions",
        schema="evaluation",
        type_="foreignkey",
    )
    op.drop_column("suite_versions", "parent_version_id", schema="evaluation")
    op.drop_column("suites", "archived_by", schema="evaluation")
    op.drop_column("suites", "archived_at", schema="evaluation")
    op.drop_column("datasets", "archived_by", schema="evaluation")
    op.drop_column("datasets", "archived_at", schema="evaluation")
