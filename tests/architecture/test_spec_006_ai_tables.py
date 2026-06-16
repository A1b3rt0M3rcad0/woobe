from __future__ import annotations

from pathlib import Path

from src.modules.agent.infra.database.preflight import (
    capture_preflight_snapshot,
    check_target_table_conflicts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
MIGRATION_FILE = MIGRATIONS_DIR / "0015_move_ai_tables_to_agent.py"

AI_BUSINESS_TABLES = [
    "provider_credentials",
    "agents",
    "agent_prompts",
    "agent_contracts",
    "agent_model_configs",
    "agent_releases",
    "agent_release_tests",
]


def _read_migration_text() -> str:
    assert MIGRATION_FILE.exists(), (
        f"Migration file not found: {MIGRATION_FILE}"
    )
    return MIGRATION_FILE.read_text(encoding="utf-8")


class TestMigrationFileExists:
    def test_migration_0015_exists(self):
        assert MIGRATION_FILE.exists(), (
            f"Migration 0015 not found at {MIGRATION_FILE}"
        )

    def test_migration_revises_0014(self):
        text = _read_migration_text()
        assert "down_revision = \"0014\"" in text, (
            "Migration must revise 0014"
        )

    def test_migration_revision_is_0015(self):
        text = _read_migration_text()
        assert "revision = \"0015\"" in text, (
            "Migration revision must be 0015"
        )


class TestAiBusinessTablesMoved:
    def test_all_ai_business_tables_in_migration(self):
        text = _read_migration_text()
        for table in AI_BUSINESS_TABLES:
            assert f"ALTER TABLE ai.{table} SET SCHEMA agent" in text, (
                f"Migration missing SET SCHEMA for ai.{table}"
            )

    def test_each_table_has_compat_view(self):
        text = _read_migration_text()
        for table in AI_BUSINESS_TABLES:
            assert f"CREATE OR REPLACE VIEW ai.{table}" in text, (
                f"Missing compat view for ai.{table}"
            )

    def test_all_tables_have_downgrade(self):
        text = _read_migration_text()
        for table in AI_BUSINESS_TABLES:
            assert f"DROP VIEW IF EXISTS ai.{table}" in text, (
                f"Missing DROP VIEW for ai.{table} in downgrade"
            )
            assert f"ALTER TABLE agent.{table} SET SCHEMA ai" in text, (
                f"Missing reverse SET SCHEMA for agent.{table} in downgrade"
            )

    def test_messaging_tables_not_included(self):
        text = _read_migration_text()
        assert "ALTER TABLE ai.outbox_events" not in text, (
            "Migration should NOT move ai.outbox_events (messaging table)"
        )
        assert "ALTER TABLE ai.inbox_events" not in text, (
            "Migration should NOT move ai.inbox_events (messaging table)"
        )


class TestPreflightAfterMove:
    def test_move_count_reflects_ai_business_tables(self):
        snapshot = capture_preflight_snapshot()
        ai_tables = [t for t, s in snapshot["table_schemas"].items() if s == "ai"]
        assert len(ai_tables) == 7, (
            f"Expected 7 ai-schema business tables in preflight, "
            f"found {len(ai_tables)}: {ai_tables}"
        )

    def test_no_agent_schema_conflicts(self):
        conflicts = check_target_table_conflicts()
        assert len(conflicts) == 0, (
            f"Unexpected conflicts: {conflicts}"
        )

    def test_ai_business_tables_in_move_list(self):
        snapshot = capture_preflight_snapshot()
        for table in AI_BUSINESS_TABLES:
            assert table in snapshot["table_schemas"], (
                f"Table {table} missing from preflight schema map"
            )
            assert snapshot["table_schemas"][table] == "ai", (
                f"Table {table} expected schema 'ai', "
                f"got '{snapshot['table_schemas'][table]}'"
            )
