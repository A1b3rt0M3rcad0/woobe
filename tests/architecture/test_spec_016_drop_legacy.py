"""Tests for spec 016 — drop legacy views, tables, and schemas.

Validates migration 0020 file structure and content.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "packages" / "woobe-db" / "migrations" / "versions"
MIGRATION_0020 = MIGRATIONS_DIR / "0020_drop_legacy_schemas.py"
AGENT_MODELS = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "infra"
    / "database"
    / "models.py"
)


class TestMigration0020Exists:
    def test_migration_0020_file_exists(self):
        assert MIGRATION_0020.exists(), "Migration 0020 file does not exist"

    def test_migration_0020_revises_0019(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        assert 'down_revision = "0019"' in text

    def test_migration_0020_revision_is_0020(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        assert 'revision = "0020"' in text


class TestMigration0020DropsLegacySchemas:
    def test_upgrade_drops_ai_views(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        assert "DROP VIEW IF EXISTS ai." in text

    def test_upgrade_drops_knowledge_views(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        assert "DROP VIEW IF EXISTS knowledge." in text

    def test_upgrade_drops_runtime_views(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        assert "DROP VIEW IF EXISTS runtime." in text

    def test_upgrade_has_all_ai_view_names(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        for view in (
            "provider_credentials", "agents", "agent_prompts", "agent_contracts",
            "agent_model_configs", "agent_releases", "agent_release_tests",
        ):
            assert view in text, f"AI view {view} not referenced in migration"

    def test_upgrade_has_all_knowledge_view_names(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        for view in (
            "document_collections", "agent_collections", "documents",
            "document_chunks", "knowledge_versions",
        ):
            assert view in text, f"Knowledge view {view} not referenced in migration"

    def test_upgrade_has_all_runtime_view_names(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        for view in ("sessions", "messages", "ask_jobs"):
            assert view in text, f"Runtime view {view} not referenced in migration"

    def test_upgrade_drops_schemas(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        assert re.search(r'DROP\s+SCHEMA\s+IF\s+EXISTS\s+ai', text, re.I)
        assert re.search(r'DROP\s+SCHEMA\s+IF\s+EXISTS\s+knowledge', text, re.I)
        assert re.search(r'DROP\s+SCHEMA\s+IF\s+EXISTS\s+runtime', text, re.I)

    def test_no_cascade(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
        assert "CASCADE" not in upgrade, "Upgrade must not use CASCADE"


class TestMigration0020Downgrade:
    def test_downgrade_recreates_schemas(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        assert "CREATE SCHEMA IF NOT EXISTS ai" in text
        assert "CREATE SCHEMA IF NOT EXISTS knowledge" in text
        assert "CREATE SCHEMA IF NOT EXISTS runtime" in text

    def test_downgrade_has_create_view(self):
        text = MIGRATION_0020.read_text(encoding="utf-8")
        downgrade = text.split("def downgrade")[1]
        assert "CREATE VIEW" in downgrade


class TestAgentTablesPreserved:
    def test_agent_tables_unaffected_in_core_models(self):
        text = AGENT_MODELS.read_text(encoding="utf-8")
        assert re.search(r'schema["\s]*[:=]["\s]*"agent"', text), (
            "No schema='agent' reference found in models.py"
        )
