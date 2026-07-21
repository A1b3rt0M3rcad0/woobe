"""harden evaluation execution persistence

Revision ID: 0055
Revises: 0054
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("request_idempotency_key", sa.String(length=255), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "uq_evaluation_runs_project_idempotency",
        "runs",
        ["project_id", "request_idempotency_key"],
        unique=True,
        schema="evaluation",
        postgresql_where=sa.text("request_idempotency_key IS NOT NULL"),
    )

    op.add_column(
        "trials",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        schema="evaluation",
    )
    op.add_column(
        "trials",
        sa.Column("runtime_completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "trials",
        sa.Column("judge_started_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "trials",
        sa.Column("judge_completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )

    op.create_check_constraint(
        "ck_evaluation_test_cases_weight",
        "test_cases",
        "weight > 0",
        schema="evaluation",
    )
    op.create_check_constraint(
        "ck_evaluation_test_cases_frequency",
        "test_cases",
        "production_frequency IS NULL OR (production_frequency >= 0 AND production_frequency <= 1)",
        schema="evaluation",
    )
    op.create_unique_constraint(
        "uq_evaluation_check_results_identity",
        "check_results",
        ["evaluation_trial_id", "evaluator_type", "evaluator_key"],
        schema="evaluation",
    )
    op.create_unique_constraint(
        "uq_evaluation_model_calls_trial",
        "model_calls",
        ["evaluation_trial_id"],
        schema="evaluation",
    )
    op.create_unique_constraint(
        "uq_evaluation_estimates_run_target",
        "estimate_runs",
        ["evaluation_run_id", "target_id"],
        schema="evaluation",
    )
    op.create_unique_constraint(
        "uq_evaluation_qualification_run_target",
        "release_qualifications",
        ["evaluation_run_id", "target_snapshot_hash"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_evaluation_qualification_run_target",
        "release_qualifications",
        schema="evaluation",
        type_="unique",
    )
    op.drop_constraint(
        "uq_evaluation_estimates_run_target",
        "estimate_runs",
        schema="evaluation",
        type_="unique",
    )
    op.drop_constraint(
        "uq_evaluation_model_calls_trial",
        "model_calls",
        schema="evaluation",
        type_="unique",
    )
    op.drop_constraint(
        "uq_evaluation_check_results_identity",
        "check_results",
        schema="evaluation",
        type_="unique",
    )
    op.drop_constraint(
        "ck_evaluation_test_cases_frequency",
        "test_cases",
        schema="evaluation",
        type_="check",
    )
    op.drop_constraint(
        "ck_evaluation_test_cases_weight",
        "test_cases",
        schema="evaluation",
        type_="check",
    )

    op.drop_column("trials", "judge_completed_at", schema="evaluation")
    op.drop_column("trials", "judge_started_at", schema="evaluation")
    op.drop_column("trials", "runtime_completed_at", schema="evaluation")
    op.drop_column("trials", "attempt", schema="evaluation")

    op.drop_index(
        "uq_evaluation_runs_project_idempotency",
        table_name="runs",
        schema="evaluation",
    )
    op.drop_column("runs", "request_idempotency_key", schema="evaluation")
