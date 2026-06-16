from __future__ import annotations

from pathlib import Path

from src.modules.agent.infra.database.preflight import (
    capture_preflight_snapshot,
    check_target_table_conflicts,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
MIGRATION_FILE = MIGRATIONS_DIR / "0017_move_runtime_tables_to_agent.py"

RUNTIME_BUSINESS_TABLES = [
    "sessions",
    "messages",
    "ask_jobs",
]


def _read_migration_text() -> str:
    assert MIGRATION_FILE.exists(), (
        f"Migration file not found: {MIGRATION_FILE}"
    )
    return MIGRATION_FILE.read_text(encoding="utf-8")


class TestMigrationFileExists:
    def test_migration_0017_exists(self):
        assert MIGRATION_FILE.exists(), (
            f"Migration 0017 not found at {MIGRATION_FILE}"
        )

    def test_migration_revises_0016(self):
        text = _read_migration_text()
        assert "down_revision = \"0016\"" in text, (
            "Migration must revise 0016"
        )

    def test_migration_revision_is_0017(self):
        text = _read_migration_text()
        assert "revision = \"0017\"" in text, (
            "Migration revision must be 0017"
        )


class TestRuntimeBusinessTablesMoved:
    def test_all_runtime_business_tables_in_migration(self):
        text = _read_migration_text()
        for table in RUNTIME_BUSINESS_TABLES:
            assert f"ALTER TABLE runtime.{table} SET SCHEMA agent" in text, (
                f"Migration missing SET SCHEMA for runtime.{table}"
            )

    def test_each_table_has_compat_view(self):
        text = _read_migration_text()
        for table in RUNTIME_BUSINESS_TABLES:
            assert f"CREATE OR REPLACE VIEW runtime.{table}" in text, (
                f"Missing compat view for runtime.{table}"
            )

    def test_all_tables_have_downgrade(self):
        text = _read_migration_text()
        for table in RUNTIME_BUSINESS_TABLES:
            assert f"DROP VIEW IF EXISTS runtime.{table}" in text, (
                f"Missing DROP VIEW for runtime.{table} in downgrade"
            )
            assert f"ALTER TABLE agent.{table} SET SCHEMA runtime" in text, (
                f"Missing reverse SET SCHEMA for agent.{table} in downgrade"
            )

    def test_messaging_tables_not_included(self):
        text = _read_migration_text()
        assert "ALTER TABLE runtime.outbox_events" not in text, (
            "Migration should NOT move runtime.outbox_events"
        )
        assert "ALTER TABLE runtime.inbox_events" not in text, (
            "Migration should NOT move runtime.inbox_events"
        )


class TestPreflightAfterRuntimeMove:
    def test_runtime_business_tables_in_preflight(self):
        snapshot = capture_preflight_snapshot()
        runtime_tables = [
            t for t, s in snapshot["table_schemas"].items() if s == "runtime"
        ]
        assert len(runtime_tables) == 5, (
            f"Expected 5 runtime-schema tables in preflight, "
            f"found {len(runtime_tables)}: {runtime_tables}"
        )

    def test_no_agent_schema_conflicts(self):
        conflicts = check_target_table_conflicts()
        assert len(conflicts) == 0, (
            f"Unexpected conflicts: {conflicts}"
        )

    def test_runtime_tables_in_move_list(self):
        snapshot = capture_preflight_snapshot()
        for table in RUNTIME_BUSINESS_TABLES:
            assert table in snapshot["table_schemas"], (
                f"Table {table} missing from preflight schema map"
            )
            assert snapshot["table_schemas"][table] == "runtime", (
                f"Table {table} expected schema 'runtime', "
                f"got '{snapshot['table_schemas'][table]}'"
            )
