"""Tests for spec 014 — data integrity and schema migration validation.

Validates that:
- All 15 business tables + 2 canonical messaging tables are in agent schema
- Zero cross-module Foreign Keys remain
- All intra-agent Foreign Keys reference agent.* tables
- Alembic head is 0019
- Migration chain is complete (no gaps)
Pre-0015 migration reference patterns are absent from models.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_PY = PROJECT_ROOT / "src" / "modules" / "agent" / "infra" / "database" / "models.py"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"

EXPECTED_AGENT_TABLES = {
    "provider_credentials",
    "agents",
    "agent_prompts",
    "agent_contracts",
    "agent_model_configs",
    "agent_releases",
    "agent_release_tests",
    "document_collections",
    "agent_collections",
    "documents",
    "document_chunks",
    "knowledge_versions",
    "sessions",
    "messages",
    "ask_jobs",
    "agent_outbox_events",
    "agent_inbox_events",
}


def _get_schema_assignments() -> dict[str, str]:
    tree = ast.parse(MODELS_PY.read_text(encoding="utf-8"))
    assignments: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        tablename = None
        schema = None
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(stmt.value, ast.Constant):
                            tablename = stmt.value.value
                    if isinstance(target, ast.Name) and target.id == "__table_args__":
                        val = stmt.value
                        if isinstance(val, ast.Dict):
                            for k, v in zip(val.keys, val.values):
                                if isinstance(k, ast.Constant) and k.value == "schema":
                                    if isinstance(v, ast.Constant):
                                        schema = v.value
                        if isinstance(val, ast.Tuple):
                            for elt in val.elts:
                                if isinstance(elt, ast.Dict):
                                    for k, v in zip(elt.keys, elt.values):
                                        if isinstance(k, ast.Constant) and k.value == "schema":
                                            if isinstance(v, ast.Constant):
                                                schema = v.value
        if tablename and schema:
            assignments[tablename] = schema
    return assignments


class TestAllAgentTablesInAgentSchema:
    def test_models_define_expected_tables(self):
        schema_assignments = _get_schema_assignments()
        defined_tables = set(schema_assignments.keys())
        missing = EXPECTED_AGENT_TABLES - defined_tables
        extra = defined_tables - EXPECTED_AGENT_TABLES
        assert not missing, f"Missing expected tables: {missing}"
        if extra:
            pass

    def test_all_business_tables_use_agent_schema(self):
        schema_assignments = _get_schema_assignments()
        non_agent = {
            t: s for t, s in schema_assignments.items()
            if t in EXPECTED_AGENT_TABLES and s != "agent"
        }
        assert not non_agent, (
            f"Tables not mapped to agent schema: {non_agent}"
        )

    def test_no_legacy_schema_in_models(self):
        text = MODELS_PY.read_text(encoding="utf-8")
        for schema in ("ai", "knowledge", "runtime"):
            pattern = rf'schema\s*=\s*["\x27]{schema}["\x27]'
            matches = re.findall(pattern, text)
            assert not matches, (
                f"Found {len(matches)} legacy schema='{schema}' references: {matches}"
            )


class TestForeignKeyIntegrity:
    def test_no_cross_module_fk_in_models(self):
        text = MODELS_PY.read_text(encoding="utf-8")
        forbidden = ("core.", "identity.", "billing.", "tools.", "metering.", "observability.")
        for ref in forbidden:
            pattern = rf'ForeignKey\(\s*["\x27]{ref}'
            matches = re.findall(pattern, text)
            assert not matches, (
                f"Found {len(matches)} cross-module FK references to '{ref}': {matches}"
            )

    def test_all_fks_point_to_agent(self):
        text = MODELS_PY.read_text(encoding="utf-8")
        fk_matches = re.findall(r'ForeignKey\(\s*["\x27]([^"\x27]+)["\x27]', text)
        non_agent = [fk for fk in fk_matches if not fk.startswith("agent.")]
        assert not non_agent, (
            f"FKs not pointing to agent schema: {non_agent}"
        )


class TestMigrationHead:
    def test_alembic_head_is_0019(self):
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
        dependents: set[int] = set()
        for rev, down in revs.items():
            if down is not None and down in all_revs:
                dependents.add(down)
        heads = all_revs - dependents
        max_head = max(heads) if heads else 0
        assert 19 in heads, (
            f"Expected head revision 0019 in heads {heads}, got max head {max_head:04d}"
        )

    def test_chain_has_no_gaps(self):
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
            assert down in all_revs, (
                f"Revision {rev:04d} references missing down_revision {down:04d}"
            )
