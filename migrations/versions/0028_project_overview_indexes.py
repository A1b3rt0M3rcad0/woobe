"""add project overview trace indexes

Revision ID: 0028
Revises: 0027
"""

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_observability_traces_project_started_terminal",
        "traces",
        ["project_id", "started_at"],
        unique=False,
        schema="observability",
        postgresql_where="status IN ('completed', 'failed', 'cancelled')",
    )
    op.create_index(
        "ix_observability_trace_events_project_created_tool",
        "trace_events",
        ["project_id", "created_at"],
        unique=False,
        schema="observability",
        postgresql_where="event_type = 'tool_call'",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_observability_trace_events_project_created_tool",
        table_name="trace_events",
        schema="observability",
    )
    op.drop_index(
        "ix_observability_traces_project_started_terminal",
        table_name="traces",
        schema="observability",
    )
