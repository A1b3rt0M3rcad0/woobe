"""add multi-environment evaluations

Revision ID: 0054
Revises: 0053
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


UUID = sa.Uuid
JSONB = postgresql.JSONB


def _base_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS evaluation")

    op.create_table(
        "datasets",
        *_base_columns(),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("current_version_id", UUID(), nullable=True),
        sa.Column("created_by", UUID(), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_datasets_project_status",
        "datasets",
        ["project_id", "status", "updated_at"],
        schema="evaluation",
    )
    op.create_index(
        "uq_evaluation_datasets_project_name",
        "datasets",
        ["project_id", sa.text("lower(btrim(name))")],
        unique=True,
        schema="evaluation",
    )

    op.create_table(
        "dataset_versions",
        *_base_columns(),
        sa.Column(
            "dataset_id",
            UUID(),
            sa.ForeignKey("evaluation.datasets.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("created_by", UUID(), nullable=True),
        sa.UniqueConstraint(
            "dataset_id",
            "version",
            name="uq_evaluation_dataset_versions_version",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_dataset_versions_project_created",
        "dataset_versions",
        ["project_id", "created_at"],
        schema="evaluation",
    )

    op.create_table(
        "test_cases",
        *_base_columns(),
        sa.Column(
            "dataset_version_id",
            UUID(),
            sa.ForeignKey("evaluation.dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("input_payload", JSONB(), nullable=False),
        sa.Column("initial_context", JSONB(), nullable=True),
        sa.Column("expected_contract", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("production_frequency", sa.Float(), nullable=True),
        sa.UniqueConstraint(
            "dataset_version_id",
            "position",
            name="uq_evaluation_test_cases_position",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_test_cases_version",
        "test_cases",
        ["dataset_version_id", "position"],
        schema="evaluation",
    )

    op.create_table(
        "suites",
        *_base_columns(),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("current_version_id", UUID(), nullable=True),
        sa.Column("created_by", UUID(), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_suites_project_status",
        "suites",
        ["project_id", "status", "updated_at"],
        schema="evaluation",
    )
    op.create_index(
        "uq_evaluation_suites_project_name",
        "suites",
        ["project_id", sa.text("lower(btrim(name))")],
        unique=True,
        schema="evaluation",
    )

    op.create_table(
        "suite_versions",
        *_base_columns(),
        sa.Column(
            "suite_id",
            UUID(),
            sa.ForeignKey("evaluation.suites.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column(
            "dataset_version_id",
            UUID(),
            sa.ForeignKey("evaluation.dataset_versions.id"),
            nullable=False,
        ),
        sa.Column("judge_provider_model_id", UUID(), nullable=False),
        sa.Column("judge_config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("rubric", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("deterministic_checks", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("acceptance_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("repetition_policy", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("estimate_defaults", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("suite_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", UUID(), nullable=True),
        sa.UniqueConstraint(
            "suite_id",
            "version",
            name="uq_evaluation_suite_versions_version",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_suite_versions_project_created",
        "suite_versions",
        ["project_id", "created_at"],
        schema="evaluation",
    )

    op.create_table(
        "runs",
        *_base_columns(),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column(
            "suite_version_id",
            UUID(),
            sa.ForeignKey("evaluation.suite_versions.id"),
            nullable=False,
        ),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("execution_order", sa.String(length=32), nullable=False, server_default="paired_interleaved"),
        sa.Column("randomization_seed", sa.Integer(), nullable=False),
        sa.Column("candidate_target_id", UUID(), nullable=True),
        sa.Column("baseline_target_id", UUID(), nullable=True),
        sa.Column("parent_run_id", UUID(), sa.ForeignKey("evaluation.runs.id"), nullable=True),
        sa.Column("requested_by", UUID(), nullable=True),
        sa.Column("qualification_status", sa.String(length=64), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("pass_rate", sa.Float(), nullable=True),
        sa.Column("aggregate_result", JSONB(), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("estimated_preflight_cost", sa.Numeric(18, 10), nullable=True),
        sa.Column("measured_total_cost", sa.Numeric(18, 10), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "repetitions BETWEEN 1 AND 25",
            name="ck_evaluation_runs_repetitions",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_runs_project_created",
        "runs",
        ["project_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_runs_status_created",
        "runs",
        ["status", "created_at"],
        schema="evaluation",
    )

    op.create_table(
        "targets",
        *_base_columns(),
        sa.Column(
            "evaluation_run_id",
            UUID(),
            sa.ForeignKey("evaluation.runs.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("side", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", UUID(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("agent_release_id", UUID(), nullable=True),
        sa.Column("network_version_id", UUID(), nullable=True),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("composition_hash", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("display_version", sa.String(length=128), nullable=False),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "side",
            name="uq_evaluation_targets_run_side",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_targets_entity",
        "targets",
        ["project_id", "target_type", "entity_id"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_targets_snapshot_hash",
        "targets",
        ["project_id", "snapshot_hash"],
        schema="evaluation",
    )

    op.create_table(
        "trials",
        *_base_columns(),
        sa.Column(
            "evaluation_run_id",
            UUID(),
            sa.ForeignKey("evaluation.runs.id"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_target_id",
            UUID(),
            sa.ForeignKey("evaluation.targets.id"),
            nullable=False,
        ),
        sa.Column(
            "test_case_id",
            UUID(),
            sa.ForeignKey("evaluation.test_cases.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("repetition", sa.Integer(), nullable=False),
        sa.Column("pair_key", sa.String(length=255), nullable=False),
        sa.Column("execution_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("agent_run_id", UUID(), nullable=True),
        sa.Column("network_execution_id", UUID(), nullable=True),
        sa.Column("root_trace_id", UUID(), nullable=True),
        sa.Column("output_payload", JSONB(), nullable=True),
        sa.Column("metrics", JSONB(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "evaluation_target_id",
            "test_case_id",
            "repetition",
            name="uq_evaluation_trials_identity",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_trials_run_status",
        "trials",
        ["evaluation_run_id", "status", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_trials_pair",
        "trials",
        ["evaluation_run_id", "pair_key"],
        schema="evaluation",
    )

    op.create_table(
        "check_results",
        *_base_columns(),
        sa.Column(
            "evaluation_trial_id",
            UUID(),
            sa.ForeignKey("evaluation.trials.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("evaluator_key", sa.String(length=128), nullable=False),
        sa.Column("evaluator_type", sa.String(length=32), nullable=False),
        sa.Column("dimension", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence", JSONB(), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_check_results_trial",
        "check_results",
        ["evaluation_trial_id", "created_at"],
        schema="evaluation",
    )

    op.create_table(
        "model_calls",
        *_base_columns(),
        sa.Column(
            "evaluation_run_id",
            UUID(),
            sa.ForeignKey("evaluation.runs.id"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_trial_id",
            UUID(),
            sa.ForeignKey("evaluation.trials.id"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("provider_model_id", UUID(), nullable=False),
        sa.Column("provider_credential_id", UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("judge_config_hash", sa.String(length=64), nullable=False),
        sa.Column("rubric_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(18, 10), nullable=True),
        sa.Column("cost_status", sa.String(length=32), nullable=True),
        sa.Column("cost_reason", sa.Text(), nullable=True),
        sa.Column("pricing_snapshot", JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("structured_result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_model_calls_run",
        "model_calls",
        ["evaluation_run_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_model_calls_trial",
        "model_calls",
        ["evaluation_trial_id"],
        schema="evaluation",
    )

    op.create_table(
        "estimate_runs",
        *_base_columns(),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column(
            "evaluation_run_id",
            UUID(),
            sa.ForeignKey("evaluation.runs.id"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            UUID(),
            sa.ForeignKey("evaluation.targets.id"),
            nullable=False,
        ),
        sa.Column("volume_unit", sa.String(length=64), nullable=False, server_default="runs_per_month"),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("assumptions", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("observation_summary", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("price_snapshot", JSONB(), nullable=True),
        sa.Column("scenarios", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("limitations", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", UUID(), nullable=True),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_estimates_run",
        "estimate_runs",
        ["evaluation_run_id", "created_at"],
        schema="evaluation",
    )

    op.create_table(
        "release_qualifications",
        *_base_columns(),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", UUID(), nullable=False),
        sa.Column("target_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("agent_release_id", UUID(), nullable=True),
        sa.Column("network_version_id", UUID(), nullable=True),
        sa.Column(
            "suite_version_id",
            UUID(),
            sa.ForeignKey("evaluation.suite_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "dataset_version_id",
            UUID(),
            sa.ForeignKey("evaluation.dataset_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "evaluation_run_id",
            UUID(),
            sa.ForeignKey("evaluation.runs.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("pass_rate", sa.Float(), nullable=True),
        sa.Column("critical_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_qualifications_target",
        "release_qualifications",
        ["project_id", "target_type", "entity_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_qualifications_snapshot",
        "release_qualifications",
        ["project_id", "target_snapshot_hash"],
        schema="evaluation",
    )

    op.create_foreign_key(
        "fk_evaluation_datasets_current_version",
        "datasets",
        "dataset_versions",
        ["current_version_id"],
        ["id"],
        source_schema="evaluation",
        referent_schema="evaluation",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_evaluation_suites_current_version",
        "suites",
        "suite_versions",
        ["current_version_id"],
        ["id"],
        source_schema="evaluation",
        referent_schema="evaluation",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_evaluation_runs_candidate_target",
        "runs",
        "targets",
        ["candidate_target_id"],
        ["id"],
        source_schema="evaluation",
        referent_schema="evaluation",
        use_alter=True,
    )
    op.create_foreign_key(
        "fk_evaluation_runs_baseline_target",
        "runs",
        "targets",
        ["baseline_target_id"],
        ["id"],
        source_schema="evaluation",
        referent_schema="evaluation",
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_evaluation_runs_baseline_target",
        "runs",
        schema="evaluation",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_runs_candidate_target",
        "runs",
        schema="evaluation",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_suites_current_version",
        "suites",
        schema="evaluation",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_evaluation_datasets_current_version",
        "datasets",
        schema="evaluation",
        type_="foreignkey",
    )

    for table_name in (
        "release_qualifications",
        "estimate_runs",
        "model_calls",
        "check_results",
        "trials",
        "targets",
        "runs",
        "suite_versions",
        "suites",
        "test_cases",
        "dataset_versions",
        "datasets",
    ):
        op.drop_table(table_name, schema="evaluation")

    op.execute("DROP SCHEMA IF EXISTS evaluation")
