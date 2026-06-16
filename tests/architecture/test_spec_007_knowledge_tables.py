from __future__ import annotations

from pathlib import Path

from src.modules.agent.infra.database.preflight import (
    capture_preflight_snapshot,
    check_target_table_conflicts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
MIGRATION_FILE = MIGRATIONS_DIR / "0016_move_knowledge_tables_to_agent.py"

KNOWLEDGE_BUSINESS_TABLES = [
    "document_collections",
    "agent_collections",
    "documents",
    "document_chunks",
    "knowledge_versions",
]


def _read_migration_text() -> str:
    assert MIGRATION_FILE.exists(), (
        f"Migration file not found: {MIGRATION_FILE}"
    )
    return MIGRATION_FILE.read_text(encoding="utf-8")


class TestMigrationFileExists:
    def test_migration_0016_exists(self):
        assert MIGRATION_FILE.exists(), (
            f"Migration 0016 not found at {MIGRATION_FILE}"
        )

    def test_migration_revises_0015(self):
        text = _read_migration_text()
        assert "down_revision = \"0015\"" in text, (
            "Migration must revise 0015"
        )

    def test_migration_revision_is_0016(self):
        text = _read_migration_text()
        assert "revision = \"0016\"" in text, (
            "Migration revision must be 0016"
        )


class TestKnowledgeBusinessTablesMoved:
    def test_all_knowledge_business_tables_in_migration(self):
        text = _read_migration_text()
        for table in KNOWLEDGE_BUSINESS_TABLES:
            assert f"ALTER TABLE knowledge.{table} SET SCHEMA agent" in text, (
                f"Migration missing SET SCHEMA for knowledge.{table}"
            )

    def test_each_table_has_compat_view(self):
        text = _read_migration_text()
        for table in KNOWLEDGE_BUSINESS_TABLES:
            assert f"CREATE OR REPLACE VIEW knowledge.{table}" in text, (
                f"Missing compat view for knowledge.{table}"
            )

    def test_all_tables_have_downgrade(self):
        text = _read_migration_text()
        for table in KNOWLEDGE_BUSINESS_TABLES:
            assert f"DROP VIEW IF EXISTS knowledge.{table}" in text, (
                f"Missing DROP VIEW for knowledge.{table} in downgrade"
            )
            assert f"ALTER TABLE agent.{table} SET SCHEMA knowledge" in text, (
                f"Missing reverse SET SCHEMA for agent.{table} in downgrade"
            )

    def test_messaging_tables_not_included(self):
        text = _read_migration_text()
        assert "ALTER TABLE knowledge.outbox_events" not in text, (
            "Migration should NOT move knowledge.outbox_events"
        )
        assert "ALTER TABLE knowledge.inbox_events" not in text, (
            "Migration should NOT move knowledge.inbox_events"
        )


class TestPreflightAfterKnowledgeMove:
    def test_knowledge_business_tables_in_preflight(self):
        snapshot = capture_preflight_snapshot()
        knowledge_tables = [
            t for t, s in snapshot["table_schemas"].items() if s == "knowledge"
        ]
        assert len(knowledge_tables) == 5, (
            f"Expected 5 knowledge-schema tables in preflight, "
            f"found {len(knowledge_tables)}: {knowledge_tables}"
        )

    def test_no_agent_schema_conflicts(self):
        conflicts = check_target_table_conflicts()
        assert len(conflicts) == 0, (
            f"Unexpected conflicts: {conflicts}"
        )

    def test_knowledge_tables_in_move_list(self):
        snapshot = capture_preflight_snapshot()
        for table in KNOWLEDGE_BUSINESS_TABLES:
            assert table in snapshot["table_schemas"], (
                f"Table {table} missing from preflight schema map"
            )
            assert snapshot["table_schemas"][table] == "knowledge", (
                f"Table {table} expected schema 'knowledge', "
                f"got '{snapshot['table_schemas'][table]}'"
            )
