"""Tests for spec 010 — cross-module Foreign Key removal.

Validates that:
- No agent model contains ForeignKey to core.projects or identity.users.
- No external module model contains ForeignKey to ai/knowledge/runtime schemas.
- Allowlist entries with removal_spec:010 have been removed.
- Migration 0018 exists with expected drop_foreign_key operations.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_MODULES = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules"
AGENT_MODELS = CORE_MODULES / "agent" / "infra" / "database" / "models.py"
METERING_MODELS = CORE_MODULES / "metering" / "infra" / "database" / "models.py"
OBSERVABILITY_MODELS = CORE_MODULES / "observability" / "infra" / "database" / "models.py"
TOOLS_MODELS = CORE_MODULES / "tools" / "infra" / "database" / "models.py"
MIGRATIONS_DIR = PROJECT_ROOT / "packages" / "woobe-db" / "migrations" / "versions"
SCHEMA_ALLOWLIST_FILE = PROJECT_ROOT / "tests" / "architecture" / "legacy_schema_allowlist.yaml"

_CROSS_MODULE_FK_PATTERN = re.compile(r'ForeignKey\s*\(\s*["\'](core|identity)\.')
_LEGACY_FK_PATTERN = re.compile(r'ForeignKey\s*\(\s*["\'](ai|knowledge|runtime)\.')


class TestNoCrossModuleFKsInAgentModels:
    """Agent models must not contain FK constraints to core or identity."""

    def test_agent_has_no_core_fk(self):
        if not AGENT_MODELS.exists():
            return
        text = AGENT_MODELS.read_text(encoding="utf-8")
        matches = _CROSS_MODULE_FK_PATTERN.findall(text)
        assert len(matches) == 0, (
            f"Agent models contain cross-module ForeignKey references: {matches}"
        )

    def test_agent_has_no_identity_fk(self):
        if not AGENT_MODELS.exists():
            return
        text = AGENT_MODELS.read_text(encoding="utf-8")
        matches = _CROSS_MODULE_FK_PATTERN.findall(text)
        assert len(matches) == 0, (
            f"Agent models contain ForeignKey to identity: {matches}"
        )


class TestNoLegacyFKsInExternalModules:
    """External modules must not contain FK constraints to legacy agent schemas."""

    EXTERNAL_MODELS = [METERING_MODELS, OBSERVABILITY_MODELS, TOOLS_MODELS]

    def test_external_modules_have_no_legacy_fk(self):
        for mod_path in self.EXTERNAL_MODELS:
            if not mod_path.exists():
                continue
            text = mod_path.read_text(encoding="utf-8")
            matches = _LEGACY_FK_PATTERN.findall(text)
            rel_path = mod_path.relative_to(PROJECT_ROOT).as_posix()
            assert len(matches) == 0, (
                f"{rel_path} contains {len(matches)} legacy FK reference(s): {matches}"
            )


class TestAllowlistRemovedSpec010:
    """Allowlist entries with removal_spec 010 must be absent."""

    def test_no_removal_spec_010_entries(self):
        if not SCHEMA_ALLOWLIST_FILE.exists():
            return
        with open(SCHEMA_ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("entries") or []
        spec_010_entries = [e for e in entries if e.get("removal_spec") == "010"]
        assert len(spec_010_entries) == 0, (
            f"Expected zero removal_spec:010 entries, found {len(spec_010_entries)}"
        )


class TestMigration0018Exists:
    """Migration 0018 must exist with FK drop operations."""

    def test_migration_0018_file_exists(self):
        candidates = list(MIGRATIONS_DIR.glob("0018*.py"))
        assert len(candidates) >= 1, (
            "Migration 0018 file not found in packages/woobe-db/migrations/versions/"
        )

    def test_migration_0018_has_drop_foreignkey(self):
        candidates = sorted(MIGRATIONS_DIR.glob("0018*.py"))
        if not candidates:
            return
        text = candidates[0].read_text(encoding="utf-8")
        assert "drop_constraint" in text, (
            "Migration 0018 must use op.drop_constraint to remove FKs"
        )
        assert "type_=\"foreignkey\"" in text or "type_='foreignkey'" in text, (
            "Migration 0018 must specify type_='foreignkey'"
        )

    def test_migration_0018_revises_0017(self):
        candidates = sorted(MIGRATIONS_DIR.glob("0018*.py"))
        if not candidates:
            return
        text = candidates[0].read_text(encoding="utf-8")
        rev_match = re.search(r'down_revision\s*=\s*["\'](\d+)["\']', text)
        assert rev_match is not None, "Migration 0018 must declare down_revision"
        assert rev_match.group(1) == "0017", (
            f"Migration 0018 should revise 0017, got {rev_match.group(1)}"
        )

    def test_migration_0018_covers_all_expected_drops(self):
        candidates = sorted(MIGRATIONS_DIR.glob("0018*.py"))
        if not candidates:
            return
        text = candidates[0].read_text(encoding="utf-8")
        expected_tables = [
            "provider_credentials",
            "agents",
            "agent_prompts",
            "agent_contracts",
            "agent_model_configs",
            "agent_releases",
            "agent_release_tests",
            "document_collections",
            "documents",
            "document_chunks",
            "knowledge_versions",
            "sessions",
            "messages",
            "ask_jobs",
        ]
        for table in expected_tables:
            assert table in text, f"Migration 0018 must handle table {table}"
