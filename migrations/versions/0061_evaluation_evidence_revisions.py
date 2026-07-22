"""add evaluation evidence revisions

Revision ID: 0061
Revises: 0060
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column(
            "evidence_revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        schema="evaluation",
    )

    op.add_column(
        "target_decisions",
        sa.Column(
            "evidence_revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        schema="evaluation",
    )
    op.add_column(
        "target_decisions",
        sa.Column("assessment_hash", sa.String(length=64), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "target_decisions",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.add_column(
        "target_decisions",
        sa.Column("superseded_reason", sa.Text(), nullable=True),
        schema="evaluation",
    )
    op.drop_constraint(
        "uq_evaluation_target_decisions_run_target",
        "target_decisions",
        schema="evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_evaluation_target_decisions_run_target_revision",
        "target_decisions",
        ["evaluation_run_id", "target_id", "evidence_revision"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_target_decisions_current",
        "target_decisions",
        ["evaluation_run_id", "target_id", "superseded_at", "evidence_revision"],
        schema="evaluation",
    )

    op.add_column(
        "estimate_runs",
        sa.Column(
            "evidence_revision",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        schema="evaluation",
    )
    op.add_column(
        "estimate_runs",
        sa.Column(
            "origin",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        schema="evaluation",
    )
    op.add_column(
        "estimate_runs",
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        schema="evaluation",
    )
    op.drop_constraint(
        "uq_evaluation_estimates_run_target_volume_price",
        "estimate_runs",
        schema="evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_evaluation_estimates_run_target_volume_price_revision",
        "estimate_runs",
        [
            "evaluation_run_id",
            "target_id",
            "volume",
            "volume_unit",
            "price_snapshot_hash",
            "evidence_revision",
        ],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_estimates_revision",
        "estimate_runs",
        ["evaluation_run_id", "evidence_revision", "created_at"],
        schema="evaluation",
    )


def downgrade() -> None:
    # Keep only the latest record per legacy uniqueness key before restoring
    # the older constraints.
    op.execute(
        """
        DELETE FROM evaluation.target_decisions current_row
        USING evaluation.target_decisions newer_row
        WHERE current_row.evaluation_run_id = newer_row.evaluation_run_id
          AND current_row.target_id = newer_row.target_id
          AND (
            current_row.evidence_revision < newer_row.evidence_revision
            OR (
              current_row.evidence_revision = newer_row.evidence_revision
              AND current_row.decided_at < newer_row.decided_at
            )
          )
        """
    )
    op.execute(
        """
        DELETE FROM evaluation.estimate_runs current_row
        USING evaluation.estimate_runs newer_row
        WHERE current_row.evaluation_run_id = newer_row.evaluation_run_id
          AND current_row.target_id = newer_row.target_id
          AND current_row.volume = newer_row.volume
          AND current_row.volume_unit = newer_row.volume_unit
          AND current_row.price_snapshot_hash = newer_row.price_snapshot_hash
          AND (
            current_row.evidence_revision < newer_row.evidence_revision
            OR (
              current_row.evidence_revision = newer_row.evidence_revision
              AND current_row.created_at < newer_row.created_at
            )
          )
        """
    )

    op.drop_index(
        "ix_evaluation_estimates_revision",
        table_name="estimate_runs",
        schema="evaluation",
    )
    op.drop_constraint(
        "uq_evaluation_estimates_run_target_volume_price_revision",
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
    op.drop_column("estimate_runs", "superseded_at", schema="evaluation")
    op.drop_column("estimate_runs", "origin", schema="evaluation")
    op.drop_column("estimate_runs", "evidence_revision", schema="evaluation")

    op.drop_index(
        "ix_evaluation_target_decisions_current",
        table_name="target_decisions",
        schema="evaluation",
    )
    op.drop_constraint(
        "uq_evaluation_target_decisions_run_target_revision",
        "target_decisions",
        schema="evaluation",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_evaluation_target_decisions_run_target",
        "target_decisions",
        ["evaluation_run_id", "target_id"],
        schema="evaluation",
    )
    op.drop_column("target_decisions", "superseded_reason", schema="evaluation")
    op.drop_column("target_decisions", "superseded_at", schema="evaluation")
    op.drop_column("target_decisions", "assessment_hash", schema="evaluation")
    op.drop_column("target_decisions", "evidence_revision", schema="evaluation")

    op.drop_column("runs", "evidence_revision", schema="evaluation")
