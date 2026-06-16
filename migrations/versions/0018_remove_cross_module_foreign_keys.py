"""remove cross-module Foreign Key constraints from agent tables

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-16
"""
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

AGENT_CORE_TABLES: list[tuple[str, str, str]] = [
    # (tablename, column, referent)
    ("provider_credentials", "project_id", "core.projects.id"),
    ("agents", "project_id", "core.projects.id"),
    ("agent_prompts", "project_id", "core.projects.id"),
    ("agent_contracts", "project_id", "core.projects.id"),
    ("agent_model_configs", "project_id", "core.projects.id"),
    ("agent_releases", "project_id", "core.projects.id"),
    ("agent_release_tests", "project_id", "core.projects.id"),
    ("document_collections", "project_id", "core.projects.id"),
    ("documents", "project_id", "core.projects.id"),
    ("document_chunks", "project_id", "core.projects.id"),
    ("knowledge_versions", "project_id", "core.projects.id"),
    ("sessions", "project_id", "core.projects.id"),
    ("messages", "project_id", "core.projects.id"),
    ("ask_jobs", "project_id", "core.projects.id"),
]

AGENT_IDENTITY_TABLES: list[tuple[str, str, str]] = [
    ("agent_prompts", "created_by", "identity.users.id"),
    ("agent_releases", "created_by", "identity.users.id"),
    ("agent_releases", "promoted_by", "identity.users.id"),
]

EXTERNAL_LEGACY_TABLES: list[tuple[str, str, str, str]] = [
    # (schema, tablename, column, referent)
    ("metering", "usage_events", "agent_id", "ai.agents.id"),
    ("metering", "usage_daily_agent", "agent_id", "ai.agents.id"),
    ("observability", "traces", "agent_id", "ai.agents.id"),
    ("observability", "traces", "session_id", "runtime.sessions.id"),
    ("tools", "tools", "agent_id", "ai.agents.id"),
]


def upgrade() -> None:
    # Drop agent -> core FKs
    for table, column, _ in AGENT_CORE_TABLES:
        _drop_fk(table, column, schema="agent")

    # Drop agent -> identity FKs
    for table, column, _ in AGENT_IDENTITY_TABLES:
        _drop_fk(table, column, schema="agent")

    # Drop external module -> legacy agent FKs
    for sch, table, column, _ in EXTERNAL_LEGACY_TABLES:
        _drop_fk(table, column, schema=sch)


def downgrade() -> None:
    # Restore external module -> agent FKs
    for sch, table, column, referent in EXTERNAL_LEGACY_TABLES:
        _create_fk(table, column, referent, schema=sch)

    # Restore agent -> identity FKs
    for table, column, referent in AGENT_IDENTITY_TABLES:
        _create_fk(table, column, referent, schema="agent")

    # Restore agent -> core FKs
    for table, column, referent in AGENT_CORE_TABLES:
        _create_fk(table, column, referent, schema="agent")


def _fk_name(table: str, column: str) -> str:
    return f"{table}_{column}_fkey"


def _drop_fk(table: str, column: str, schema: str) -> None:
    op.drop_constraint(
        _fk_name(table, column),
        table,
        schema=schema,
        type_="foreignkey",
    )


def _create_fk(table: str, column: str, referent: str, schema: str) -> None:
    op.create_foreign_key(
        _fk_name(table, column),
        table,
        referent,
        [column],
        ["id"],
        source_schema=schema,
    )
