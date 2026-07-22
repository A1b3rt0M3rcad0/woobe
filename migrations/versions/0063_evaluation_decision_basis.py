"""record evaluation decision basis

Revision ID: 0063
Revises: 0062
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "target_decisions",
        sa.Column(
            "decision_basis",
            sa.String(length=32),
            nullable=False,
            server_default="evidence",
        ),
        schema="evaluation",
    )
    op.create_check_constraint(
        "ck_evaluation_target_decisions_basis",
        "target_decisions",
        "decision_basis IN ('evidence', 'manual_override')",
        schema="evaluation",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_evaluation_target_decisions_basis",
        "target_decisions",
        schema="evaluation",
        type_="check",
    )
    op.drop_column("target_decisions", "decision_basis", schema="evaluation")
