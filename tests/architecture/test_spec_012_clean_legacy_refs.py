"""Tests for spec 012 — no legacy schema references remain in executable code.

Validates that:
- No production code in packages/woobe-core/src references schema="ai|knowledge|runtime".
- No production code imports from modules.ai|knowledge|runtime.
- Allowlist only covers historical migrations (removal_spec: 016).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SCHEMA_ALLOWLIST = PROJECT_ROOT / "tests" / "architecture" / "legacy_schema_allowlist.yaml"

_MODULE_IMPORT_PATTERN = re.compile(r'(from|import)\s+modules\.(ai|knowledge|runtime)')


class TestNoLegacySchemaRefsInSource:
    def test_no_schema_ai_in_source(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
            text = py_file.read_text(encoding="utf-8")
            assert '"schema": "ai"' not in text, (
                f"{rel} contains schema='ai' reference"
            )

    def test_no_schema_knowledge_in_source(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
            text = py_file.read_text(encoding="utf-8")
            assert '"schema": "knowledge"' not in text, (
                f"{rel} contains schema='knowledge' reference"
            )

    def test_no_schema_runtime_in_source(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
            text = py_file.read_text(encoding="utf-8")
            assert '"schema": "runtime"' not in text, (
                f"{rel} contains schema='runtime' reference"
            )


class TestNoLegacyModuleImportsInSource:
    def _assert_no_legacy_import(self, module_name: str) -> None:
        for py_file in SRC_DIR.rglob("*.py"):
            rel = py_file.relative_to(PROJECT_ROOT).as_posix()
            text = py_file.read_text(encoding="utf-8")
            for match_type, module in _MODULE_IMPORT_PATTERN.findall(text):
                if module == module_name:
                    assert False, (
                        f"{rel} contains import from modules.{module_name}: {match_type}"
                    )

    def test_no_ai_module_imports(self):
        self._assert_no_legacy_import("ai")

    def test_no_knowledge_module_imports(self):
        self._assert_no_legacy_import("knowledge")

    def test_no_runtime_module_imports(self):
        self._assert_no_legacy_import("runtime")


class TestAllowlistOnlyHistorical:
    def test_allowlist_only_removal_spec_016(self):
        if not SCHEMA_ALLOWLIST.exists():
            return
        with open(SCHEMA_ALLOWLIST, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("entries") or []
        for entry in entries:
            spec = entry.get("removal_spec", "")
            reason = entry.get("reason", "")
            assert spec == "016", (
                f"Allowlist entry with removal_spec='{spec}' should not exist for executable code: {reason}"
            )
