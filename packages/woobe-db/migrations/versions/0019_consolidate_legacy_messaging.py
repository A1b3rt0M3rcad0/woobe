"""consolidate legacy Outbox/Inbox tables from ai/knowledge/runtime schemas

Pre-migration steps (requires PostgreSQL access):
  1. Count and verify events: SELECT status, count(*) FROM ai.outbox_events GROUP BY status;
  2. For pending/retryable events, copy to agent.agent_outbox_events with
     canonical envelope mapping (preserving idempotency_key, correlation_id,
     causation_id).
  3. Mark copied events as migrated in source table.
  4. Export completed/processed/dead events to audit archive if retention
     policy requires.
  5. Confirm zero rows in all six legacy tables before this migration runs.
  6. If events remain, pause and execute the data-migration script first.

This migration is the contract phase: it drops the six legacy messaging
tables (ai.outbox_events, ai.inbox_events, knowledge.outbox_events,
knowledge.inbox_events, runtime.outbox_events, runtime.inbox_events)
after data has been migrated to agent.agent_outbox_events and
agent.agent_inbox_events.

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

LEGACY_SCHEMAS = ["ai", "knowledge", "runtime"]
LEGACY_OUTBOX_TABLES = [
    (schema, "outbox_events") for schema in LEGACY_SCHEMAS
]
LEGACY_INBOX_TABLES = [
    (schema, "inbox_events") for schema in LEGACY_SCHEMAS
]


def _create_outbox_table(table_name: str, schema: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("event_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="'{}'"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=schema,
    )


def _create_inbox_table(table_name: str, schema: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("outbox_origin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("event_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="'{}'"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("consumer_name", sa.String(128), nullable=True),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("causation_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=schema,
    )


def upgrade() -> None:
    for schema, table_name in LEGACY_OUTBOX_TABLES:
        op.drop_table(table_name, schema=schema)
    for schema, table_name in LEGACY_INBOX_TABLES:
        op.drop_table(table_name, schema=schema)


def downgrade() -> None:
    for schema, table_name in LEGACY_OUTBOX_TABLES:
        _create_outbox_table(table_name, schema)
    for schema, table_name in LEGACY_INBOX_TABLES:
        _create_inbox_table(table_name, schema)
