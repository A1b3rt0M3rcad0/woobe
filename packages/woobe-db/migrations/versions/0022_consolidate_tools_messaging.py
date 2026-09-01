"""consolidate tools legacy outbox and inbox into agent canonical tables

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-16
"""
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Copy pending/retryable outbox events from tools schema to agent
    op.execute(
        "INSERT INTO agent.agent_outbox_events "
        "(id, aggregate_type, aggregate_id, event_type, event_version, routing_key, "
        " payload, idempotency_key, correlation_id, causation_id, status, attempts, "
        " available_at, locked_at, locked_by, published_at, error, created_at, updated_at) "
        "SELECT "
        "  o.id, o.aggregate_type, o.aggregate_id, o.event_type, "
        "  COALESCE(o.event_version, 1), "
        "  CASE "
        "    WHEN o.event_type LIKE 'tools.tool.%' THEN replace(o.event_type, 'tools.tool.', 'agent.tool.') || '.v1' "
        "    WHEN o.event_type LIKE 'tools.secret.%' THEN replace(o.event_type, 'tools.secret.', 'agent.secret.') || '.v1' "
        "    ELSE o.event_type "
        "  END, "
        "  o.payload, "
        "  o.id::text, COALESCE(o.correlation_id, gen_random_uuid()), o.causation_id, "
        "  o.status, o.attempts, o.available_at, NULL::timestamptz, NULL::varchar, "
        "  o.published_at, o.error, o.created_at, o.updated_at "
        "FROM tools.outbox_events o "
        "WHERE o.status IN ('pending', 'retryable') "
        "ON CONFLICT (idempotency_key) DO NOTHING"
    )

    # Mark copied tools events as migrated
    op.execute(
        "UPDATE tools.outbox_events SET status = 'migrated' "
        "WHERE status IN ('pending', 'retryable') "
        "AND id IN (SELECT o.id FROM tools.outbox_events o "
        "           JOIN agent.agent_outbox_events a ON a.idempotency_key = o.id::text)"
    )

    # Copy pending/retryable inbox events from tools schema to agent
    op.execute(
        "INSERT INTO agent.agent_inbox_events "
        "(id, message_id, producer_module, consumer_module, event_type, event_version, "
        " routing_key, payload, headers, idempotency_key, correlation_id, causation_id, "
        " status, attempts, available_at, locked_at, locked_by, processed_at, error, "
        " created_at, updated_at) "
        "SELECT "
        "  i.id, "
        "  COALESCE(i.outbox_origin_id::text, i.id::text), "
        "  'tools', 'agent', "
        "  i.event_type, COALESCE(i.event_version, 1), "
        "  CASE "
        "    WHEN i.event_type LIKE 'tools.tool.%' THEN replace(i.event_type, 'tools.tool.', 'agent.tool.') || '.v1' "
        "    WHEN i.event_type LIKE 'tools.secret.%' THEN replace(i.event_type, 'tools.secret.', 'agent.secret.') || '.v1' "
        "    ELSE i.event_type "
        "  END, "
        "  i.payload, NULL::jsonb, "
        "  i.id::text, COALESCE(i.correlation_id, gen_random_uuid()), i.causation_id, "
        "  i.status, i.attempts, i.available_at, NULL::timestamptz, NULL::varchar, "
        "  i.processed_at, i.error, i.created_at, i.updated_at "
        "FROM tools.inbox_events i "
        "WHERE i.status IN ('received', 'retryable') "
        "ON CONFLICT (idempotency_key) DO NOTHING"
    )

    # Mark copied tools inbox events as migrated
    op.execute(
        "UPDATE tools.inbox_events SET status = 'migrated' "
        "WHERE status IN ('received', 'retryable') "
        "AND id IN (SELECT i.id FROM tools.inbox_events i "
        "           JOIN agent.agent_inbox_events a ON a.idempotency_key = i.id::text)"
    )

    # Archive completed/processed/dead outbox events (older than 7 days)
    op.execute(
        "UPDATE tools.outbox_events SET status = 'archived' "
        "WHERE status IN ('published', 'dead') "
        "AND updated_at < NOW() - INTERVAL '7 days'"
    )

    # Archive completed/processed/dead inbox events (older than 7 days)
    op.execute(
        "UPDATE tools.inbox_events SET status = 'archived' "
        "WHERE status IN ('processed', 'dead', 'ignored') "
        "AND updated_at < NOW() - INTERVAL '7 days'"
    )

    # Rename legacy tables and create compatibility views in tools schema
    op.execute("ALTER TABLE tools.outbox_events RENAME TO outbox_events_migrated")
    op.execute("CREATE VIEW tools.outbox_events AS SELECT * FROM agent.agent_outbox_events")
    op.execute("ALTER TABLE tools.inbox_events RENAME TO inbox_events_migrated")
    op.execute("CREATE VIEW tools.inbox_events AS SELECT * FROM agent.agent_inbox_events")


def downgrade() -> None:
    # Drop compatibility views
    op.execute("DROP VIEW IF EXISTS tools.outbox_events")
    op.execute("DROP VIEW IF EXISTS tools.inbox_events")

    # Restore legacy tables from renamed originals (if they exist)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE tools.outbox_events_migrated RENAME TO outbox_events;
        EXCEPTION WHEN undefined_table THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE tools.inbox_events_migrated RENAME TO inbox_events;
        EXCEPTION WHEN undefined_table THEN NULL;
        END $$
    """)

    # Reverse archived/migrated status
    op.execute("UPDATE tools.outbox_events SET status = 'published' WHERE status = 'archived' AND published_at IS NOT NULL")
    op.execute("UPDATE tools.outbox_events SET status = 'dead' WHERE status = 'archived' AND published_at IS NULL")
    op.execute("UPDATE tools.outbox_events SET status = 'pending' WHERE status = 'migrated'")
    op.execute("UPDATE tools.inbox_events SET status = 'processed' WHERE status = 'archived' AND processed_at IS NOT NULL")
    op.execute("UPDATE tools.inbox_events SET status = 'dead' WHERE status = 'archived' AND processed_at IS NULL")
    op.execute("UPDATE tools.inbox_events SET status = 'received' WHERE status = 'migrated'")

    # Delete copied events from agent tables
    op.execute(
        "DELETE FROM agent.agent_outbox_events "
        "WHERE idempotency_key IN (SELECT id::text FROM tools.outbox_events WHERE status IN ('pending', 'retryable', 'published', 'dead'))"
    )
    op.execute(
        "DELETE FROM agent.agent_inbox_events "
        "WHERE idempotency_key IN (SELECT id::text FROM tools.inbox_events WHERE status IN ('received', 'retryable', 'processed', 'dead'))"
    )
