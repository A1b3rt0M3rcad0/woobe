"""persist immutable evaluation evidence revisions

Revision ID: 0064
Revises: 0063
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_revisions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("assessment_hash", sa.String(length=64), nullable=True),
        sa.Column("evidence_status", sa.String(length=32), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_reason", sa.String(length=64), nullable=False),
        sa.Column("captured_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evaluation_run_id"],
            ["evaluation.runs.id"],
            name="fk_evaluation_evidence_revisions_run",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "revision",
            name="uq_evaluation_evidence_revisions_run_revision",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_evidence_revisions_project",
        "evidence_revisions",
        ["project_id", "created_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_evidence_revisions_run",
        "evidence_revisions",
        ["evaluation_run_id", "revision"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_evidence_revisions_run",
        table_name="evidence_revisions",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_evidence_revisions_project",
        table_name="evidence_revisions",
        schema="evaluation",
    )
    op.drop_table("evidence_revisions", schema="evaluation")
