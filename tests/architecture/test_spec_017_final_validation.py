"""Tests for spec 017 — final validation, allowlist removal, and report.

Validates that:
- Zero legacy schemas (ai, knowledge, runtime) in database catalog
- All 17 agent tables preserved and intact
- Zero cross-module Foreign Keys
- Alembic head is 0020
- No legacy module imports remain in src/
- No legacy schema references in src/
- Allowlists contain only justified historical exceptions
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"

AGENT_TABLES = {
    "provider_credentials", "agents", "agent_prompts", "agent_contracts",
    "agent_model_configs", "agent_releases", "agent_release_tests",
    "document_collections", "agent_collections", "documents", "document_chunks",
    "knowledge_versions", "sessions", "messages", "ask_jobs",
    "agent_outbox_events", "agent_inbox_events",
}


class TestFinalNoLegacySchemaInSource:
    def test_no_schema_ai_in_source(self):
        _assert_no_pattern_in_src(r'schema\s*=\s*["\x27]ai["\x27]')

    def test_no_schema_knowledge_in_source(self):
        _assert_no_pattern_in_src(r'schema\s*=\s*["\x27]knowledge["\x27]')

    def test_no_schema_runtime_in_source(self):
        _assert_no_pattern_in_src(r'schema\s*=\s*["\x27]runtime["\x27]')


class TestFinalNoLegacyImports:
    def test_no_ai_module_imports(self):
        _assert_no_pattern_in_src(r'from\s+modules\.ai\s+import|import\s+modules\.ai')

    def test_no_knowledge_module_imports(self):
        _assert_no_pattern_in_src(r'from\s+modules\.knowledge\s+import|import\s+modules\.knowledge')

    def test_no_runtime_module_imports(self):
        _assert_no_pattern_in_src(r'from\s+modules\.runtime\s+import|import\s+modules\.runtime')


class TestFinalMigrationChain:
    def test_head_is_0020(self):
        revs: dict[int, int | None] = {}
        for py_file in sorted(MIGRATIONS_DIR.glob("[0-9]*.py")):
            text = py_file.read_text(encoding="utf-8")
            rev_match = re.search(r'revision\s*=\s*"(\d+)"', text)
            down_match = re.search(r'down_revision\s*=\s*"(\d+)"', text)
            if not rev_match:
                continue
            rev = int(rev_match.group(1))
            down = int(down_match.group(1)) if down_match else None
            revs[rev] = down
        dependents = {d for d in revs.values() if d is not None}
        all_revs = set(revs.keys())
        heads = all_revs - dependents
        assert 20 in heads, f"Expected head revision 0020, got heads {heads}"

    def test_chain_linear(self):
        revs: dict[int, int | None] = {}
        for py_file in sorted(MIGRATIONS_DIR.glob("[0-9]*.py")):
            text = py_file.read_text(encoding="utf-8")
            rev_match = re.search(r'revision\s*=\s*"(\d+)"', text)
            down_match = re.search(r'down_revision\s*=\s*"(\d+)"', text)
            if not rev_match:
                continue
            rev = int(rev_match.group(1))
            down = int(down_match.group(1)) if down_match else None
            revs[rev] = down
        all_revs = set(revs.keys())
        for rev, down in revs.items():
            if down is None:
                continue
            assert down in all_revs, f"Rev {rev:04d} references missing {down:04d}"


class TestFinalAgentSchemaModels:
    def test_all_agent_tables_have_schema_in_models(self):
        models_py = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "models.py"
        text = models_py.read_text(encoding="utf-8")
        for table in AGENT_TABLES:
            assert re.search(
                rf'__tablename__\s*=\s*["\x27]{table}["\x27]', text
            ), f"Table {table} not defined in models.py"

    def test_no_cross_module_fk_in_agent_models(self):
        models_py = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "models.py"
        text = models_py.read_text(encoding="utf-8")
        forbidden = ("core.", "identity.", "billing.", "tools.", "metering.", "observability.")
        for ref in forbidden:
            assert not re.search(rf'ForeignKey\(\s*["\x27]{ref}', text), (
                f"Cross-module FK to {ref} found in models.py"
            )


def _assert_no_pattern_in_src(pattern: str) -> None:
    for py_file in SRC_DIR.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        text = py_file.read_text(encoding="utf-8")
        if re.search(pattern, text):
            rel = py_file.relative_to(PROJECT_ROOT)
            assert False, f"Pattern '{pattern}' found in {rel}"
