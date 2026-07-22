"""add evaluation catalog and comparisons

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluations",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suite_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("target_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("target_identity_hash", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("display_version", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("latest_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["suite_version_id"],
            ["evaluation.suite_versions.id"],
            name="fk_evaluation_evaluations_suite_version",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "suite_version_id",
            "target_identity_hash",
            name="uq_evaluation_catalog_identity",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_catalog_entity",
        "evaluations",
        ["project_id", "target_type", "entity_id", "updated_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_catalog_snapshot",
        "evaluations",
        ["project_id", "target_snapshot_hash", "suite_version_id"],
        schema="evaluation",
    )

    op.add_column(
        "runs",
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "runs",
        sa.Column("evaluation_protocol_hash", sa.String(length=64), nullable=True),
        schema="evaluation",
    )
    op.create_foreign_key(
        "fk_evaluation_runs_evaluation",
        "runs",
        "evaluations",
        ["evaluation_id"],
        ["id"],
        source_schema="evaluation",
        referent_schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_runs_evaluation_created",
        "runs",
        ["evaluation_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_runs_protocol",
        "runs",
        ["project_id", "evaluation_protocol_hash"],
        schema="evaluation",
    )

    op.create_table(
        "comparisons",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("suite_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("protocol_hash", sa.String(length=64), nullable=False),
        sa.Column("comparison_mode", sa.String(length=32), nullable=False),
        sa.Column("candidate_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_evidence_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reference_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference_evidence_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="waiting"),
        sa.Column("aggregate_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("request_idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "candidate_run_id <> reference_run_id",
            name="ck_evaluation_comparisons_distinct_runs",
        ),
        sa.ForeignKeyConstraint(
            ["suite_version_id"],
            ["evaluation.suite_versions.id"],
            name="fk_evaluation_comparisons_suite_version",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_run_id"],
            ["evaluation.runs.id"],
            name="fk_evaluation_comparisons_candidate_run",
        ),
        sa.ForeignKeyConstraint(
            ["reference_run_id"],
            ["evaluation.runs.id"],
            name="fk_evaluation_comparisons_reference_run",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_run_id",
            "candidate_evidence_revision",
            "reference_run_id",
            "reference_evidence_revision",
            name="uq_evaluation_comparison_evidence_pair",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_comparisons_project_created",
        "comparisons",
        ["project_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_comparisons_status",
        "comparisons",
        ["status", "updated_at"],
        schema="evaluation",
    )
    op.create_index(
        "uq_evaluation_comparisons_project_idempotency",
        "comparisons",
        ["project_id", "request_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("request_idempotency_key IS NOT NULL"),
        schema="evaluation",
    )

    op.create_table(
        "comparison_decisions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comparison_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_evidence_revision", sa.Integer(), nullable=False),
        sa.Column("reference_evidence_revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decision_basis", sa.String(length=32), nullable=False, server_default="evidence"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["evaluation.comparisons.id"],
            name="fk_evaluation_comparison_decisions_comparison",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "comparison_id",
            "candidate_evidence_revision",
            "reference_evidence_revision",
            name="uq_evaluation_comparison_decision_revisions",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_comparison_decisions_project",
        "comparison_decisions",
        ["project_id", "decided_at"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_comparison_decisions_project",
        table_name="comparison_decisions",
        schema="evaluation",
    )
    op.drop_table("comparison_decisions", schema="evaluation")

    op.drop_index(
        "uq_evaluation_comparisons_project_idempotency",
        table_name="comparisons",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_comparisons_status",
        table_name="comparisons",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_comparisons_project_created",
        table_name="comparisons",
        schema="evaluation",
    )
    op.drop_table("comparisons", schema="evaluation")

    op.drop_index("ix_evaluation_runs_protocol", table_name="runs", schema="evaluation")
    op.drop_index(
        "ix_evaluation_runs_evaluation_created",
        table_name="runs",
        schema="evaluation",
    )
    op.drop_constraint(
        "fk_evaluation_runs_evaluation",
        "runs",
        schema="evaluation",
        type_="foreignkey",
    )
    op.drop_column("runs", "evaluation_protocol_hash", schema="evaluation")
    op.drop_column("runs", "evaluation_id", schema="evaluation")

    op.drop_index(
        "ix_evaluation_catalog_snapshot",
        table_name="evaluations",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_catalog_entity",
        table_name="evaluations",
        schema="evaluation",
    )
    op.drop_table("evaluations", schema="evaluation")
