"""remove tools schema, compatibility views, and messaging tables

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-16
"""
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop compatibility views in tools schema
    op.execute("DROP VIEW IF EXISTS tools.tools")
    op.execute("DROP VIEW IF EXISTS tools.secrets")
    op.execute("DROP VIEW IF EXISTS tools.outbox_events")
    op.execute("DROP VIEW IF EXISTS tools.inbox_events")
    # Drop renamed legacy tables (left over from migration 0022 rename)
    op.execute("DROP TABLE IF EXISTS tools.outbox_events_migrated")
    op.execute("DROP TABLE IF EXISTS tools.inbox_events_migrated")
    # Drop tools schema (no CASCADE — must be empty)
    op.execute("DROP SCHEMA IF EXISTS tools")


def downgrade() -> None:
    # Recreate tools schema
    op.execute("CREATE SCHEMA IF NOT EXISTS tools")
    # Recreate compatibility views
    op.execute(
        "CREATE VIEW tools.tools AS SELECT * FROM agent.tools"
    )
    op.execute(
        "CREATE VIEW tools.secrets AS SELECT * FROM agent.tool_secrets"
    )
    op.execute(
        "CREATE VIEW tools.outbox_events AS SELECT * FROM agent.agent_outbox_events"
    )
    op.execute(
        "CREATE VIEW tools.inbox_events AS SELECT * FROM agent.agent_inbox_events"
    )
