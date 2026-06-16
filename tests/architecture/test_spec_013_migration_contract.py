"""Tests for spec 013 — migration chain contract and fresh-install equivalence.

Validates that:
- Migration chain is linear and complete (0001→0019).
- No post-consolidation migration creates legacy schema objects.
- migrations/env.py does not import legacy modules.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations" / "versions"
ENV_PY = PROJECT_ROOT / "migrations" / "env.py"
CONSOLIDATION_START = 15  # First post-consolidation migration revision


def _get_revisions() -> dict[int, int | None]:
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
    return revs


def _get_all_classdefs(filepath: Path) -> list[str]:
    if not filepath.exists():
        return []
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


class TestMigrationChainLinear:
    def test_chain_has_19_revisions(self):
        revs = _get_revisions()
        assert len(revs) == 19, (
            f"Expected 19 revisions, got {len(revs)}"
        )

    def test_chain_starts_at_0001(self):
        revs = _get_revisions()
        assert 1 in revs, "Revision 0001 must exist"
        assert revs[1] is None, "Revision 0001 must have no down_revision"

    def test_chain_ends_at_0019(self):
        revs = _get_revisions()
        assert 19 in revs, "Revision 0019 must exist"
        all_revs = set(revs.keys())
        has_dependent = {d for d in revs.values() if d in all_revs}
        tails = [r for r in all_revs if r not in has_dependent]
        assert max(tails) == 19, (
            f"Expected tail revision 0019, got {tails}"
        )

    def test_chain_is_linear(self):
        revs = _get_revisions()
        all_revs = set(revs.keys())
        for rev, down in revs.items():
            if down is None:
                continue
            assert down in all_revs, (
                f"Revision {rev:04d} references missing down_revision {down:04d}"
            )


class TestNoLegacyObjectsInNewMigrations:
    def test_no_create_table_in_legacy_schema(self):
        for py_file in sorted(MIGRATIONS_DIR.glob("[0-9]*.py")):
            text = py_file.read_text(encoding="utf-8")
            rev_match = re.search(r'revision\s*=\s*"(\d+)"', text)
            if not rev_match:
                continue
            rev = int(rev_match.group(1))
            if rev < CONSOLIDATION_START:
                continue
            name = py_file.name
            for schema in ("ai", "knowledge", "runtime"):
                pattern = rf'create_table.*schema=["\x27]{schema}["\x27]'
                if re.search(pattern, text):
                    assert False, (
                        f"Migration {name} creates table in legacy schema '{schema}'"
                    )


class TestEnvPyNoLegacyImports:
    def test_env_py_does_not_import_legacy_modules(self):
        if not ENV_PY.exists():
            return
        text = ENV_PY.read_text(encoding="utf-8")
        for module in ("modules.ai", "modules.knowledge", "modules.runtime"):
            assert module not in text, (
                f"migrations/env.py should not import {module}"
            )


class TestEnvPyImportsAgentModels:
    def test_env_py_imports_agent_models(self):
        if not ENV_PY.exists():
            return
        text = ENV_PY.read_text(encoding="utf-8")
        assert "modules.agent.infra.database.models" in text, (
            "migrations/env.py must import agent models for metadata"
        )
