"""drop legacy compat views and schemas (ai, knowledge, runtime)

Contract migration: removes temporary compatibility views created by
migrations 0015-0017 and drops the legacy schemas.

Preconditions:
  - All application code references only agent.* tables.
  - No production queries reference ai.*, knowledge.*, or runtime.* views.
  - Zero rows remain in legacy messaging tables (verified by migration 0019).
  - No functions, types, sequences, or policies exist in these schemas.

Warning:
  Downgrade is destructive without a restore. Data is preserved in agent.*
  tables, but the legacy schemas are recreated empty. This is intentional:
  rollback from contract phase requires restore or compensatory migration.

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

AI_VIEWS = [
    "provider_credentials",
    "agents",
    "agent_prompts",
    "agent_contracts",
    "agent_model_configs",
    "agent_releases",
    "agent_release_tests",
]

KNOWLEDGE_VIEWS = [
    "document_collections",
    "agent_collections",
    "documents",
    "document_chunks",
    "knowledge_versions",
]

RUNTIME_VIEWS = [
    "sessions",
    "messages",
    "ask_jobs",
]


def upgrade() -> None:
    for view in AI_VIEWS:
        op.execute(f"DROP VIEW IF EXISTS ai.{view}")
    for view in KNOWLEDGE_VIEWS:
        op.execute(f"DROP VIEW IF EXISTS knowledge.{view}")
    for view in RUNTIME_VIEWS:
        op.execute(f"DROP VIEW IF EXISTS runtime.{view}")
    op.execute("DROP SCHEMA IF EXISTS ai")
    op.execute("DROP SCHEMA IF EXISTS knowledge")
    op.execute("DROP SCHEMA IF EXISTS runtime")


def downgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ai")
    op.execute("CREATE SCHEMA IF NOT EXISTS knowledge")
    op.execute("CREATE SCHEMA IF NOT EXISTS runtime")
    for view in AI_VIEWS:
        op.execute(f"CREATE VIEW ai.{view} AS SELECT * FROM agent.{view}")
    for view in KNOWLEDGE_VIEWS:
        op.execute(f"CREATE VIEW knowledge.{view} AS SELECT * FROM agent.{view}")
    for view in RUNTIME_VIEWS:
        op.execute(f"CREATE VIEW runtime.{view} AS SELECT * FROM agent.{view}")
