"""fix all datetime columns to use timezone=True (TIMESTAMPTZ)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _alter_column_to_timestamptz(schema: str, table: str, column: str) -> None:
    """Alter column to TIMESTAMPTZ only if it exists and is timestamp without time zone."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t "
            "AND column_name = :c AND data_type = 'timestamp without time zone'"
        ),
        {"s": schema, "t": table, "c": column},
    )
    if result.scalar():
        conn.exec_driver_sql(
            f"ALTER TABLE {schema}.{table} "
            f"ALTER COLUMN {column} TYPE TIMESTAMPTZ "
            f"USING {column} AT TIME ZONE 'UTC'"
        )


def _alter_column_to_timestamp(schema: str, table: str, column: str) -> None:
    """Revert column to timestamp without time zone only if it exists and is timestamptz."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = :s AND table_name = :t "
            "AND column_name = :c AND data_type = 'timestamp with time zone'"
        ),
        {"s": schema, "t": table, "c": column},
    )
    if result.scalar():
        conn.exec_driver_sql(
            f"ALTER TABLE {schema}.{table} "
            f"ALTER COLUMN {column} TYPE TIMESTAMP WITHOUT TIME ZONE "
            f"USING {column} AT TIME ZONE 'UTC'"
        )


FIXES = [
    # (schema, table, column)
    # identity
    ("identity", "workspace_members", "joined_at"),
    ("identity", "workspace_invites", "expires_at"),
    ("identity", "workspace_invites", "accepted_at"),
    ("identity", "user_sessions", "revoked_at"),
    ("identity", "user_sessions", "expires_at"),
    ("identity", "user_sessions", "last_used_at"),
    # core
    ("core", "api_keys", "last_used_at"),
    ("core", "api_keys", "expires_at"),
    ("core", "api_keys", "revoked_at"),
    # ai
    ("ai", "provider_credentials", "last_validated_at"),
    # knowledge
    ("knowledge", "documents", "indexed_at"),
    # runtime
    ("runtime", "sessions", "last_message_at"),
    # billing
    ("billing", "subscriptions", "current_period_start"),
    ("billing", "subscriptions", "current_period_end"),
    ("billing", "subscriptions", "trial_ends_at"),
    ("billing", "subscriptions", "canceled_at"),
    ("billing", "payment_events", "processed_at"),
    # metering
    ("metering", "usage_daily_project", "updated_at"),
    ("metering", "usage_daily_agent", "updated_at"),
    # observability
    ("observability", "traces", "started_at"),
    ("observability", "traces", "ended_at"),
]

EVENT_SCHEMAS = [
    "identity", "core", "ai", "knowledge",
    "runtime", "tools", "metering", "billing", "observability",
]

OUTBOX_COLUMNS = ("available_at", "published_at")
INBOX_COLUMNS = ("available_at", "processed_at")


def upgrade() -> None:
    for schema, table, column in FIXES:
        _alter_column_to_timestamptz(schema, table, column)

    for schema in EVENT_SCHEMAS:
        for column in OUTBOX_COLUMNS:
            _alter_column_to_timestamptz(schema, "outbox_events", column)
        for column in INBOX_COLUMNS:
            _alter_column_to_timestamptz(schema, "inbox_events", column)


def downgrade() -> None:
    for schema, table, column in FIXES:
        _alter_column_to_timestamp(schema, table, column)

    for schema in EVENT_SCHEMAS:
        for column in OUTBOX_COLUMNS:
            _alter_column_to_timestamp(schema, "outbox_events", column)
        for column in INBOX_COLUMNS:
            _alter_column_to_timestamp(schema, "inbox_events", column)
