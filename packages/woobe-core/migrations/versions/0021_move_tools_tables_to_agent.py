"""move tools business tables to agent schema (SET SCHEMA) with compat views

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-16
"""
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop cross-module FKs before SET SCHEMA
    op.execute("ALTER TABLE tools.tools DROP CONSTRAINT IF EXISTS tools_tools_project_id_fkey")
    op.execute("ALTER TABLE tools.secrets DROP CONSTRAINT IF EXISTS tools_secrets_project_id_fkey")

    # Remove old indexes that conflict with agent schema (will be recreated)
    op.execute("DROP INDEX IF EXISTS ix_tools_tools_project_id")
    op.execute("DROP INDEX IF EXISTS ix_tools_tools_agent_id")
    op.execute("DROP INDEX IF EXISTS ix_tools_secrets_project_id")

    # Move tools.tools -> agent.tools
    op.execute("ALTER TABLE tools.tools SET SCHEMA agent")

    # Move tools.secrets -> agent.tool_secrets (rename)
    op.execute("ALTER TABLE tools.secrets SET SCHEMA agent")
    op.execute("ALTER TABLE agent.secrets RENAME TO tool_secrets")

    # Recreate indexes in agent schema
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_tools_project_id ON agent.tools (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_tools_agent_id ON agent.tools (agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_tool_secrets_project_id ON agent.tool_secrets (project_id)")

    # Create FK agent.tools.agent_id -> agent.agents.id (only if no orphans)
    op.execute(
        "DO $$ BEGIN "
        "  IF NOT EXISTS (SELECT 1 FROM agent.tools t WHERE t.agent_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM agent.agents a WHERE a.id = t.agent_id)) THEN "
        "    ALTER TABLE agent.tools ADD CONSTRAINT fk_agent_tools_agent_id FOREIGN KEY (agent_id) REFERENCES agent.agents(id); "
        "  END IF; "
        "END $$"
    )

    # Create compatibility views in tools schema for cutover period
    op.execute("CREATE OR REPLACE VIEW tools.tools AS SELECT * FROM agent.tools")
    op.execute("CREATE OR REPLACE VIEW tools.secrets AS SELECT * FROM agent.tool_secrets")


def downgrade() -> None:
    # Drop compat views
    op.execute("DROP VIEW IF EXISTS tools.tools")
    op.execute("DROP VIEW IF EXISTS tools.secrets")

    # Drop FK added in upgrade
    op.execute("ALTER TABLE agent.tools DROP CONSTRAINT IF EXISTS fk_agent_tools_agent_id")

    # Drop agent-schema indexes
    op.execute("DROP INDEX IF EXISTS ix_agent_tools_project_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_tools_agent_id")
    op.execute("DROP INDEX IF EXISTS ix_agent_tool_secrets_project_id")

    # Rename back and move to tools schema
    op.execute("ALTER TABLE agent.tool_secrets RENAME TO secrets")
    op.execute("ALTER TABLE agent.secrets SET SCHEMA tools")
    op.execute("ALTER TABLE agent.tools SET SCHEMA tools")

    # Restore old indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_tools_tools_project_id ON tools.tools (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tools_tools_agent_id ON tools.tools (agent_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tools_secrets_project_id ON tools.secrets (project_id)")

    # Cross-module FKs are not restored (they were removed intentionally)
    # The downgrade restores data and structure, but cross-module FKs are a one-way architectural improvement
