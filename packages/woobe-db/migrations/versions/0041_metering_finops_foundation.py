"""add metering finops foundation

Revision ID: 0041
Revises: 0040
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def _add_daily_columns(table_name: str) -> None:
    for name in (
        "successful_requests",
        "failed_requests",
        "cancelled_requests",
        "llm_calls",
        "priced_requests",
        "partial_cost_requests",
        "unpriced_requests",
    ):
        op.add_column(
            table_name,
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
            schema="metering",
        )
    op.add_column(
        table_name,
        sa.Column("last_event_occurred_at", sa.DateTime(timezone=True), nullable=True),
        schema="metering",
    )


def _drop_daily_columns(table_name: str) -> None:
    op.drop_column(table_name, "last_event_occurred_at", schema="metering")
    for name in reversed(
        (
            "successful_requests",
            "failed_requests",
            "cancelled_requests",
            "llm_calls",
            "priced_requests",
            "partial_cost_requests",
            "unpriced_requests",
        )
    ):
        op.drop_column(table_name, name, schema="metering")


def upgrade() -> None:
    op.add_column(
        "usage_events",
        sa.Column("source_event_id", sa.Uuid(), nullable=True),
        schema="metering",
    )
    op.add_column(
        "usage_events",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        schema="metering",
    )
    op.add_column("usage_events", sa.Column("trace_id", sa.Uuid(), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("call_id", sa.String(length=128), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("environment", sa.String(length=32), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("agent_release_id", sa.Uuid(), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("agent_release_version", sa.String(length=64), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("provider", sa.String(length=64), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("model", sa.String(length=255), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("provider_model_id", sa.Uuid(), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("input_tokens", sa.BigInteger(), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("output_tokens", sa.BigInteger(), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("cost_status", sa.String(length=32), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("cost_reason", sa.Text(), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("usage_complete", sa.Boolean(), nullable=True), schema="metering")
    op.add_column("usage_events", sa.Column("pricing_snapshot", postgresql.JSONB(), nullable=True), schema="metering")

    op.execute(
        """
        UPDATE metering.usage_events
        SET occurred_at = created_at,
            input_tokens = CASE
                WHEN COALESCE(data ->> 'input_tokens', '') ~ '^[0-9]+$'
                THEN (data ->> 'input_tokens')::bigint
                ELSE NULL
            END,
            output_tokens = CASE
                WHEN COALESCE(data ->> 'output_tokens', '') ~ '^[0-9]+$'
                THEN (data ->> 'output_tokens')::bigint
                ELSE NULL
            END,
            cost_status = CASE
                WHEN cost_usd IS NOT NULL THEN 'known'
                ELSE 'unknown'
            END
        """
    )

    op.create_index(
        "uq_metering_usage_events_source_event",
        "usage_events",
        ["source_event_id"],
        unique=True,
        schema="metering",
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )
    op.create_index(
        "ix_metering_usage_events_project_occurred",
        "usage_events",
        ["project_id", "occurred_at"],
        schema="metering",
    )
    op.create_index(
        "ix_metering_usage_events_project_trace",
        "usage_events",
        ["project_id", "trace_id"],
        schema="metering",
    )
    op.create_index(
        "ix_metering_usage_events_project_agent_occurred",
        "usage_events",
        ["project_id", "agent_id", "occurred_at"],
        schema="metering",
    )

    _add_daily_columns("usage_daily_project")
    _add_daily_columns("usage_daily_agent")


def downgrade() -> None:
    _drop_daily_columns("usage_daily_agent")
    _drop_daily_columns("usage_daily_project")

    op.drop_index("ix_metering_usage_events_project_agent_occurred", table_name="usage_events", schema="metering")
    op.drop_index("ix_metering_usage_events_project_trace", table_name="usage_events", schema="metering")
    op.drop_index("ix_metering_usage_events_project_occurred", table_name="usage_events", schema="metering")
    op.drop_index("uq_metering_usage_events_source_event", table_name="usage_events", schema="metering")

    for name in reversed(
        (
            "pricing_snapshot",
            "usage_complete",
            "cost_reason",
            "cost_status",
            "output_tokens",
            "input_tokens",
            "provider_model_id",
            "model",
            "provider",
            "agent_release_version",
            "agent_release_id",
            "environment",
            "call_id",
            "trace_id",
            "occurred_at",
            "source_event_id",
        )
    ):
        op.drop_column("usage_events", name, schema="metering")
