"""attribute evaluation runtime in observability and metering

Revision ID: 0056
Revises: 0055
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for schema, table in (("observability", "traces"), ("metering", "usage_events")):
        op.add_column(
            table,
            sa.Column(
                "run_purpose",
                sa.String(length=32),
                nullable=False,
                server_default="operational",
            ),
            schema=schema,
        )
        op.add_column(
            table,
            sa.Column("evaluation_run_id", sa.Uuid(), nullable=True),
            schema=schema,
        )
        op.add_column(
            table,
            sa.Column("evaluation_trial_id", sa.Uuid(), nullable=True),
            schema=schema,
        )
        op.add_column(
            table,
            sa.Column("comparison_pair_id", sa.String(length=255), nullable=True),
            schema=schema,
        )
        op.add_column(
            table,
            sa.Column("target_side", sa.String(length=32), nullable=True),
            schema=schema,
        )

    op.create_index(
        "ix_observability_traces_project_purpose_started",
        "traces",
        ["project_id", "run_purpose", "started_at"],
        schema="observability",
    )
    op.create_index(
        "ix_observability_traces_evaluation_run",
        "traces",
        ["evaluation_run_id", "evaluation_trial_id"],
        schema="observability",
        postgresql_where=sa.text("evaluation_run_id IS NOT NULL"),
    )
    op.create_index(
        "ix_metering_usage_events_project_purpose_occurred",
        "usage_events",
        ["project_id", "run_purpose", "occurred_at"],
        schema="metering",
    )
    op.create_index(
        "ix_metering_usage_events_evaluation_run",
        "usage_events",
        ["evaluation_run_id", "evaluation_trial_id"],
        schema="metering",
        postgresql_where=sa.text("evaluation_run_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_metering_usage_events_evaluation_run",
        table_name="usage_events",
        schema="metering",
    )
    op.drop_index(
        "ix_metering_usage_events_project_purpose_occurred",
        table_name="usage_events",
        schema="metering",
    )
    op.drop_index(
        "ix_observability_traces_evaluation_run",
        table_name="traces",
        schema="observability",
    )
    op.drop_index(
        "ix_observability_traces_project_purpose_started",
        table_name="traces",
        schema="observability",
    )

    for schema, table in (("metering", "usage_events"), ("observability", "traces")):
        op.drop_column(table, "target_side", schema=schema)
        op.drop_column(table, "comparison_pair_id", schema=schema)
        op.drop_column(table, "evaluation_trial_id", schema=schema)
        op.drop_column(table, "evaluation_run_id", schema=schema)
        op.drop_column(table, "run_purpose", schema=schema)
