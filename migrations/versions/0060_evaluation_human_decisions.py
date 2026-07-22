"""add human evaluation decisions

Revision ID: 0060
Revises: 0059
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None

UUID = sa.Uuid


def upgrade() -> None:
    op.create_table(
        "target_decisions",
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
        sa.Column("target_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decided_by", UUID(), nullable=False),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "evaluation_run_id",
            "target_id",
            name="uq_evaluation_target_decisions_run_target",
        ),
        sa.CheckConstraint(
            "decision IN ('accepted', 'rejected')",
            name="ck_evaluation_target_decisions_decision",
        ),
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_target_decisions_target",
        "target_decisions",
        ["project_id", "target_snapshot_hash", "decided_at"],
        schema="evaluation",
    )
    op.create_index(
        "ix_evaluation_target_decisions_run",
        "target_decisions",
        ["evaluation_run_id", "decided_at"],
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_target_decisions_run",
        table_name="target_decisions",
        schema="evaluation",
    )
    op.drop_index(
        "ix_evaluation_target_decisions_target",
        table_name="target_decisions",
        schema="evaluation",
    )
    op.drop_table("target_decisions", schema="evaluation")
