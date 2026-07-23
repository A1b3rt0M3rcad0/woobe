"""add session evaluation evidence and protocol-aware catalog identity

Revision ID: 0065
Revises: 0064
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluations",
        sa.Column("evaluation_protocol_hash", sa.String(length=64), nullable=True),
        schema="evaluation",
    )
    op.execute(
        """
        UPDATE evaluation.evaluations e
        SET evaluation_protocol_hash = source.evaluation_protocol_hash
        FROM (
            SELECT DISTINCT ON (evaluation_id)
                evaluation_id,
                evaluation_protocol_hash
            FROM evaluation.runs
            WHERE evaluation_id IS NOT NULL
              AND evaluation_protocol_hash IS NOT NULL
            ORDER BY evaluation_id, created_at DESC
        ) source
        WHERE e.id = source.evaluation_id
        """
    )
    op.drop_constraint(
        "uq_evaluation_catalog_identity",
        "evaluations",
        schema="evaluation",
        type_="unique",
    )
    op.create_index(
        "uq_evaluation_catalog_protocol_identity",
        "evaluations",
        [
            "project_id",
            "suite_version_id",
            "target_identity_hash",
            "evaluation_protocol_hash",
        ],
        unique=True,
        schema="evaluation",
        postgresql_where=sa.text("evaluation_protocol_hash IS NOT NULL"),
    )
    # Preserve legacy rows that predate protocol hashing without allowing future
    # protocol-aware Evaluations to collapse into them.
    op.create_index(
        "uq_evaluation_catalog_legacy_identity",
        "evaluations",
        ["project_id", "suite_version_id", "target_identity_hash"],
        unique=True,
        schema="evaluation",
        postgresql_where=sa.text("evaluation_protocol_hash IS NULL"),
    )

    op.create_table(
        "trial_turns",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_trial_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("agent_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("network_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("network_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_code", sa.String(length=128), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_trial_id"],
            ["evaluation.trials.id"],
            name="fk_evaluation_trial_turns_trial",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_trial_id",
            "position",
            name="uq_evaluation_trial_turns_position",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_trial_turns_trial",
        "trial_turns",
        ["evaluation_trial_id", "position"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_trial_turns_project",
        "trial_turns",
        ["project_id", "created_at"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_trial_turns_project",
        table_name="trial_turns",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_trial_turns_trial",
        table_name="trial_turns",
        schema="evaluation",
    )
    op.drop_table("trial_turns", schema="evaluation")

    op.drop_index(
        "uq_evaluation_catalog_legacy_identity",
        table_name="evaluations",
        schema="evaluation",
    )
    op.drop_index(
        "uq_evaluation_catalog_protocol_identity",
        table_name="evaluations",
        schema="evaluation",
    )
    op.create_unique_constraint(
        "uq_evaluation_catalog_identity",
        "evaluations",
        ["project_id", "suite_version_id", "target_identity_hash"],
        schema="evaluation",
    )
    op.drop_column("evaluations", "evaluation_protocol_hash", schema="evaluation")
