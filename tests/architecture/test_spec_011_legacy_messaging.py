"""Tests for spec 011 — legacy messaging table consolidation.

Validates that:
- Models.py no longer contains legacy messaging classes.
- All outbox writers use AgentOutboxEventModel (agent schema).
- Allowlist entries with removal_spec:011 have been removed.
- Migration 0019 exists to drop legacy messaging tables.
- Preflight no longer tracks legacy outbox/inbox entries.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_MODELS = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "models.py"
REPOSITORIES = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "repositories.py"
PREFLIGHT = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "preflight.py"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
SCHEMA_ALLOWLIST = PROJECT_ROOT / "tests" / "architecture" / "legacy_schema_allowlist.yaml"

_LEGACY_CLASSES = [
    "OutboxEventModel",
    "InboxEventModel",
    "KnowledgeOutboxEventModel",
    "KnowledgeInboxEventModel",
    "RuntimeOutboxEventModel",
    "RuntimeInboxEventModel",
]

_LEGACY_SCHEMA_PATTERN = re.compile(r'schema["\x27]\s*:\s*["\x27](ai|knowledge|runtime)["\x27]')


def _get_models_text() -> str:
    assert AGENT_MODELS.exists(), f"Models file not found: {AGENT_MODELS}"
    return AGENT_MODELS.read_text(encoding="utf-8")


class TestNoLegacyMessagingModels:
    def test_legacy_outbox_models_removed(self):
        text = _get_models_text()
        for cls_name in _LEGACY_CLASSES:
            assert f"class {cls_name}" not in text, (
                f"Legacy class {cls_name} should be removed from models.py"
            )

    def test_no_legacy_schema_in_models(self):
        text = _get_models_text()
        matches = _LEGACY_SCHEMA_PATTERN.findall(text)
        assert len(matches) == 0, (
            f"models.py still contains legacy schema references: {matches}"
        )

    def test_base_inbox_outbox_imports_removed(self):
        text = _get_models_text()
        assert "BaseInbox" not in text, "BaseInbox import should be removed"
        assert "BaseOutbox" not in text, "BaseOutbox import should be removed"


class TestConsolidatedWriterExists:
    def test_legacy_writers_removed(self):
        if not REPOSITORIES.exists():
            return
        text = REPOSITORIES.read_text(encoding="utf-8")
        assert "SQLAlchemyOutboxEventWriter" not in text, "Legacy ai outbox writer should be removed"
        assert "SQLAlchemyKnowledgeOutboxEventWriter" not in text, (
            "Legacy knowledge outbox writer should be removed"
        )
        assert "SQLAlchemyRuntimeOutboxEventWriter" not in text, (
            "Legacy runtime outbox writer should be removed"
        )

    def test_consolidated_writer_uses_agent_model(self):
        if not REPOSITORIES.exists():
            return
        text = REPOSITORIES.read_text(encoding="utf-8")
        assert "class SQLAlchemyAgentOutboxEventWriter" in text, (
            "Consolidated SQLAlchemyAgentOutboxEventWriter class should exist"
        )
        assert "AgentOutboxEventModel(" in text, (
            "Consolidated writer should use AgentOutboxEventModel"
        )


class TestAllowlistCleaned:
    def test_no_removal_spec_011_entries(self):
        if not SCHEMA_ALLOWLIST.exists():
            return
        with open(SCHEMA_ALLOWLIST, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        entries = data.get("entries") or []
        spec_011_entries = [e for e in entries if e.get("removal_spec") == "011"]
        assert len(spec_011_entries) == 0, (
            f"Allowlist should have zero removal_spec:011 entries, found {spec_011_entries}"
        )


class TestPreflightCleaned:
    def test_no_legacy_outbox_in_preflight(self):
        if not PREFLIGHT.exists():
            return
        text = PREFLIGHT.read_text(encoding="utf-8")
        # AGENT_SCHEMA_TABLES should no longer have outbox_events/inbox_events entries
        assert '"outbox_events"' not in text, (
            "Preflight should not track outbox_events entries"
        )
        assert '"inbox_events"' not in text, (
            "Preflight should not track inbox_events entries"
        )


class TestMigration0019Exists:
    def test_migration_0019_exists(self):
        mig_file = MIGRATIONS_DIR / "0019_consolidate_legacy_messaging.py"
        assert mig_file.exists(), "Migration 0019 file should exist"

    def test_migration_drops_legacy_tables(self):
        mig_file = MIGRATIONS_DIR / "0019_consolidate_legacy_messaging.py"
        if not mig_file.exists():
            return
        text = mig_file.read_text(encoding="utf-8")
        assert "op.drop_table" in text, "Migration should call op.drop_table"
        assert "downgrade" in text, "Migration should implement downgrade"
