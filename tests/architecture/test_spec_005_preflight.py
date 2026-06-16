from __future__ import annotations

from pathlib import Path

from src.modules.agent.infra.database.preflight import (
    AGENT_SCHEMA_TABLES,
    capture_preflight_snapshot,
    check_target_table_conflicts,
    collect_current_schema_assignments,
    detect_pending_migrations,
    get_migration_revisions,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestPreflightCollectCurrentSchemaAssignments:
    def test_returns_all_agent_tables(self):
        assignments = collect_current_schema_assignments()
        assert len(assignments) == 19, (
            f"Expected 19 agent-domain tables, got {len(assignments)}: {assignments}"
        )

    def test_assignments_match_expected_schemas(self):
        assignments = collect_current_schema_assignments()
        mismatches = {}
        for table, expected_schema in AGENT_SCHEMA_TABLES.items():
            if table in assignments and assignments[table] != expected_schema:
                mismatches[table] = (assignments[table], expected_schema)
        assert len(mismatches) == 0, (
            f"Schema assignment mismatches: {mismatches}"
        )

    def test_agent_and_legacy_schemas(self):
        assignments = collect_current_schema_assignments()
        schemas = set(assignments.values())
        assert "agent" in schemas
        # Legacy schemas still present for messaging tables (outbox_events/inbox_events)
        # Note: duplicate tablenames overwrite in dict, so last-writer wins
        assert len(schemas) >= 2


class TestPreflightCheckTargetTableConflicts:
    def test_no_unexpected_agent_tables(self):
        conflicts = check_target_table_conflicts()
        assert len(conflicts) == 0, (
            f"Unexpected tables in agent schema: {conflicts}"
        )


class TestPreflightDetectPendingMigrations:
    def test_no_pending_migrations(self):
        pending = detect_pending_migrations()
        assert len(pending) == 0, (
            f"Pending/orphan migrations found: {pending}"
        )

    def test_revisions_are_sorted(self):
        revisions = get_migration_revisions()
        assert len(revisions) >= 14, (
            f"Expected at least 14 migration revisions, got {len(revisions)}"
        )
        assert revisions[-1] == "0014", (
            f"Expected head revision 0014, got {revisions[-1]}"
        )


class TestPreflightSnapshot:
    def test_snapshot_contains_expected_keys(self):
        snapshot = capture_preflight_snapshot()
        expected_keys = {
            "table_schemas", "alembic_head", "all_revisions",
            "tables_to_move", "expected_move_count",
            "unexpected_agent_tables", "pending_migrations",
            "agent_schema_created_by_migration", "total_agent_tables",
        }
        missing = expected_keys - set(snapshot.keys())
        assert len(missing) == 0, (
            f"Missing keys in snapshot: {missing}"
        )

    def test_snapshot_idempotent(self):
        first = capture_preflight_snapshot()
        second = capture_preflight_snapshot()
        assert first == second, (
            "Preflight snapshot is not deterministic — "
            "calling twice produced different results"
        )

    def test_snapshot_move_count_reflects_metadata(self):
        snapshot = capture_preflight_snapshot()
        legacy_tables = [t for t, s in snapshot["table_schemas"].items() if s in ("ai", "knowledge", "runtime")]
        assert snapshot["expected_move_count"] == len(legacy_tables), (
            f"Expected {len(legacy_tables)} tables in legacy schemas, "
            f"got {snapshot['expected_move_count']}"
        )

    def test_snapshot_agent_schema_documented(self):
        snapshot = capture_preflight_snapshot()
        assert snapshot["agent_schema_created_by_migration"] == "0013"

    def test_snapshot_no_conflicts(self):
        snapshot = capture_preflight_snapshot()
        assert len(snapshot["unexpected_agent_tables"]) == 0

    def test_snapshot_no_pending(self):
        snapshot = capture_preflight_snapshot()
        assert len(snapshot["pending_migrations"]) == 0


class TestPreflightDetectionFileExists:
    def test_detection_file_created(self):
        detection = (
            PROJECT_ROOT
            / "specs"
            / "agent-schema-consolidation"
            / "execution"
            / "detection-spec-005.md"
        )
        assert detection.exists(), (
            f"Detection file missing: {detection}"
        )
        content = detection.read_text(encoding="utf-8")
        assert "Pre-move snapshot" in content
        assert "19" in content
