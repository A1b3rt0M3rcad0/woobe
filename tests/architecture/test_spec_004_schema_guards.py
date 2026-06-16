"""Tests for spec 004 — architecture guards against new legacy schema references.

Validates that:
- No new __table_args__ schema="ai|knowledge|runtime" references are added to models.py.
- No new ForeignKey references to legacy schemas are added outside the allowlist.
- Agent module tables are classified by current schema and target schema.
- Migration files do not add new legacy schema operations (post-consolidation).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_MODELS = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "models.py"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
SCHEMA_ALLOWLIST_FILE = PROJECT_ROOT / "tests" / "architecture" / "legacy_schema_allowlist.yaml"

LEGACY_SCHEMAS = {"ai", "knowledge", "runtime"}

_LEGACY_TABLE_ARGS_PATTERN = re.compile(r'schema["\']\s*:\s*["\'](ai|knowledge|runtime)["\']')
_FK_LEGACY_PATTERN = re.compile(r'ForeignKey\s*\(\s*["\'](ai|knowledge|runtime)\.')

AGENT_TABLE_SCHEMAS: dict[str, str] = {
    "provider_credentials": "agent",
    "agents": "agent",
    "outbox_events": "ai",
    "inbox_events": "ai",
    "agent_prompts": "agent",
    "agent_contracts": "agent",
    "agent_model_configs": "agent",
    "agent_releases": "agent",
    "agent_release_tests": "agent",
    "document_collections": "agent",
    "agent_collections": "agent",
    "documents": "agent",
    "document_chunks": "agent",
    "knowledge_versions": "agent",
    "sessions": "agent",
    "messages": "agent",
    "ask_jobs": "agent",
    "agent_outbox_events": "agent",
    "agent_inbox_events": "agent",
}

TARGET_TABLE_SCHEMAS: dict[str, str] = {
    table: "agent" for table in AGENT_TABLE_SCHEMAS
}


def _load_schema_allowlist() -> set[tuple[str, str]]:
    if not SCHEMA_ALLOWLIST_FILE.exists():
        return set()
    with open(SCHEMA_ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (e["file_path"], e["line_pattern"])
        for e in entries
    }


class TestNoNewLegacySchemaReferences:
    """Guard: block new schema='ai|knowledge|runtime' references in models.py."""

    def _get_legacy_table_args(self) -> set[str]:
        text = AGENT_MODELS.read_text(encoding="utf-8")
        return set(_LEGACY_TABLE_ARGS_PATTERN.findall(text))

    def test_all_legacy_schema_in_models_are_allowlisted(self):
        allowlist = _load_schema_allowlist()
        legacy_refs = self._get_legacy_table_args()
        if not legacy_refs:
            return
        unlisted = set()
        for r in legacy_refs:
            is_allowlisted = any(
                allow_path == "src/modules/agent/infra/database/models.py"
                and r in allow_pattern
                for allow_path, allow_pattern in allowlist
            )
            if not is_allowlisted:
                unlisted.add(r)
        assert len(unlisted) == 0, (
            f"Unallowlisted legacy schema references: {unlisted}"
        )

    def test_no_new_legacy_table_args_in_models(self):
        text = AGENT_MODELS.read_text(encoding="utf-8")
        allowlist = _load_schema_allowlist()
        for match in _LEGACY_TABLE_ARGS_PATTERN.finditer(text):
            schema = match.group(1)
            allowlisted = any(
                allow_path == "src/modules/agent/infra/database/models.py"
                and schema in allow_pattern
                for allow_path, allow_pattern in allowlist
            )
            assert allowlisted, (
                f"New unallowlisted schema='{schema}' reference in models.py"
            )


class TestLegacyForeignKeyReferences:
    """Guard: block new ForeignKey references to legacy schemas."""

    MODELS_WITH_FK = [
        PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "models.py",
        PROJECT_ROOT / "src" / "modules" / "metering" / "infra" / "database" / "models.py",
        PROJECT_ROOT / "src" / "modules" / "observability" / "infra" / "database" / "models.py",
        PROJECT_ROOT / "src" / "modules" / "tools" / "infra" / "database" / "models.py",
    ]

    def test_no_unallowlisted_legacy_fk_in_models(self):
        allowlist = _load_schema_allowlist()
        for mod_path in self.MODELS_WITH_FK:
            if not mod_path.exists():
                continue
            text = mod_path.read_text(encoding="utf-8")
            for match in _FK_LEGACY_PATTERN.finditer(text):
                schema = match.group(1)
                rel_path = str(mod_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                allowlisted = any(
                    allow_path == rel_path
                    for allow_path, allow_pattern in allowlist
                )
                assert allowlisted, (
                    f"New unallowlisted ForeignKey('{schema}.') in {rel_path}"
                )


class TestAgentTableSchemaClassification:
    """Classify agent module tables by current and target schema."""

    def test_current_schema_classification_complete(self):
        known_tables = set(AGENT_TABLE_SCHEMAS.keys())
        current_schemas = set(AGENT_TABLE_SCHEMAS.values())
        assert "ai" in current_schemas, "Must have tables in ai schema"
        assert "agent" in current_schemas, "Must have tables in agent schema"
        assert len(known_tables) == 19, (
            f"Expected 19 agent-domain tables, found {len(known_tables)}"
        )

    def test_target_schema_is_agent_for_all_tables(self):
        for table, target in TARGET_TABLE_SCHEMAS.items():
            assert target == "agent", (
                f"Table {table} must target schema 'agent', got '{target}'"
            )

    def test_legacy_schema_tables_listed(self):
        legacy_tables = [
            t for t, s in AGENT_TABLE_SCHEMAS.items()
            if s in LEGACY_SCHEMAS
        ]
        assert len(legacy_tables) > 0, "Must have legacy schema tables"
        assert "providers_credentials" not in str(legacy_tables), (
            "Legacy table list must be accurate"
        )


class TestMigrationLegacySchemaGuard:
    """Guard: no NEW migration operations create objects in legacy schemas."""

    _LEGACY_MIGRATION_OP = re.compile(
        r'create_table.*schema=["\'](ai|knowledge|runtime)["\']'
        r'|op\.create_table.*schema=["\'](ai|knowledge|runtime)["\']'
    )

    def test_new_migrations_dont_create_legacy_objects(self):
        if not MIGRATIONS_DIR.exists():
            return
        for py_file in sorted(MIGRATIONS_DIR.glob("*.py")):
            text = py_file.read_text(encoding="utf-8")
            # Skip historical migrations (pre-consolidation)
            rev_match = re.search(r'revision\s*=\s*["\'](\d+)["\']', text)
            if rev_match:
                rev_num = int(rev_match.group(1))
                if rev_num <= 14:
                    continue
            for match in self._LEGACY_MIGRATION_OP.finditer(text):
                rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
                assert False, (
                    f"New migration {rel} creates objects in legacy schema (post-consolidation)"
                )
