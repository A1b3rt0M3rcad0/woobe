"""standardize outbox/inbox tables across modules with canonical fields

Adds routing_key, idempotency_key, locked_at, locked_by, and metadata columns
to module-level outbox_events tables. Adds message_id, producer_module,
consumer_module, routing_key, headers, idempotency_key, locked_at, and
locked_by columns to module-level inbox_events tables.

Creates unique constraints for idempotency and message deduplication,
partial indexes for pending/retryable claims, and correlation/aggregate
indexes matching the agent canonical schema.

Only affects billing, core, identity, metering, and observability schemas.
Agent tables already have the canonical fields.

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

MODULE_SCHEMAS = ["billing", "core", "identity", "metering", "observability"]

OUTBOX_CANONICAL_COLUMNS = [
    ("routing_key", sa.String(255), False, ""),
    ("idempotency_key", sa.String(255), False, sa.text("gen_random_uuid()::text")),
    ("locked_at", sa.DateTime(timezone=True), True, None),
    ("locked_by", sa.String(128), True, None),
    ("metadata", JSONB, True, None),
]

INBOX_CANONICAL_COLUMNS = [
    ("message_id", sa.String(255), False, sa.text("gen_random_uuid()::text")),
    ("producer_module", sa.String(64), False, ""),
    ("consumer_module", sa.String(64), False, ""),
    ("routing_key", sa.String(255), False, ""),
    ("headers", JSONB, True, None),
    ("idempotency_key", sa.String(255), False, sa.text("gen_random_uuid()::text")),
    ("locked_at", sa.DateTime(timezone=True), True, None),
    ("locked_by", sa.String(128), True, None),
]


def upgrade() -> None:
    for schema in MODULE_SCHEMAS:
        _upgrade_outbox(schema)
        _upgrade_inbox(schema)


def downgrade() -> None:
    for schema in reversed(MODULE_SCHEMAS):
        _downgrade_inbox(schema)
        _downgrade_outbox(schema)


def _upgrade_outbox(schema: str) -> None:
    for col_name, col_type, nullable, server_default in OUTBOX_CANONICAL_COLUMNS:
        op.add_column(
            "outbox_events",
            sa.Column(col_name, col_type, nullable=nullable, server_default=server_default),
            schema=schema,
        )
    op.create_unique_constraint(
        f"uq_{schema}_outbox_idempotency_key",
        "outbox_events",
        ["idempotency_key"],
        schema=schema,
    )
    op.create_index(
        f"ix_{schema}_outbox_pending",
        "outbox_events",
        ["status", "available_at", "created_at"],
        schema=schema,
        postgresql_where=sa.text("status IN ('pending', 'retryable')"),
    )
    op.create_index(
        f"ix_{schema}_outbox_correlation_id",
        "outbox_events",
        ["correlation_id"],
        schema=schema,
    )
    op.create_index(
        f"ix_{schema}_outbox_aggregate",
        "outbox_events",
        ["aggregate_type", "aggregate_id"],
        schema=schema,
    )


def _upgrade_inbox(schema: str) -> None:
    for col_name, col_type, nullable, server_default in INBOX_CANONICAL_COLUMNS:
        op.add_column(
            "inbox_events",
            sa.Column(col_name, col_type, nullable=nullable, server_default=server_default),
            schema=schema,
        )
    op.create_unique_constraint(
        f"uq_{schema}_inbox_message_id",
        "inbox_events",
        ["message_id"],
        schema=schema,
    )
    op.create_unique_constraint(
        f"uq_{schema}_inbox_idempotency_key",
        "inbox_events",
        ["idempotency_key"],
        schema=schema,
    )
    op.create_index(
        f"ix_{schema}_inbox_pending",
        "inbox_events",
        ["status", "available_at", "created_at"],
        schema=schema,
        postgresql_where=sa.text("status IN ('received', 'retryable')"),
    )
    op.create_index(
        f"ix_{schema}_inbox_correlation_id",
        "inbox_events",
        ["correlation_id"],
        schema=schema,
    )


def _downgrade_outbox(schema: str) -> None:
    op.drop_index(f"ix_{schema}_outbox_aggregate", table_name="outbox_events", schema=schema)
    op.drop_index(f"ix_{schema}_outbox_correlation_id", table_name="outbox_events", schema=schema)
    op.drop_index(f"ix_{schema}_outbox_pending", table_name="outbox_events", schema=schema)
    op.drop_constraint(f"uq_{schema}_outbox_idempotency_key", "outbox_events", schema=schema)
    for col_name, _, _, _ in OUTBOX_CANONICAL_COLUMNS:
        op.drop_column("outbox_events", col_name, schema=schema)


def _downgrade_inbox(schema: str) -> None:
    op.drop_index(f"ix_{schema}_inbox_correlation_id", table_name="inbox_events", schema=schema)
    op.drop_index(f"ix_{schema}_inbox_pending", table_name="inbox_events", schema=schema)
    op.drop_constraint(f"uq_{schema}_inbox_idempotency_key", "inbox_events", schema=schema)
    op.drop_constraint(f"uq_{schema}_inbox_message_id", "inbox_events", schema=schema)
    for col_name, _, _, _ in INBOX_CANONICAL_COLUMNS:
        op.drop_column("inbox_events", col_name, schema=schema)
