"""move runtime business tables to agent schema (SET SCHEMA) with compat views

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-16
"""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS agent")
    # sessions
    op.execute("ALTER TABLE runtime.sessions SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW runtime.sessions AS SELECT * FROM agent.sessions")
    # messages
    op.execute("ALTER TABLE runtime.messages SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW runtime.messages AS SELECT * FROM agent.messages")
    # ask_jobs
    op.execute("ALTER TABLE runtime.ask_jobs SET SCHEMA agent")
    op.execute("CREATE OR REPLACE VIEW runtime.ask_jobs AS SELECT * FROM agent.ask_jobs")


def downgrade() -> None:
    # ask_jobs
    op.execute("DROP VIEW IF EXISTS runtime.ask_jobs")
    op.execute("ALTER TABLE agent.ask_jobs SET SCHEMA runtime")
    # messages
    op.execute("DROP VIEW IF EXISTS runtime.messages")
    op.execute("ALTER TABLE agent.messages SET SCHEMA runtime")
    # sessions
    op.execute("DROP VIEW IF EXISTS runtime.sessions")
    op.execute("ALTER TABLE agent.sessions SET SCHEMA runtime")
