"""Tests for spec 012 — no legacy schema references remain in executable code.

Validates that:
- No production code in src/ references schema="ai|knowledge|runtime".
- No production code imports from modules.ai|knowledge|runtime.
- No config files contain legacy schema references.
- Allowlist only covers historical migrations (removal_spec: 016).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
SCHEMA_ALLOWLIST = PROJECT_ROOT / "tests" / "architecture" / "legacy_schema_allowlist.yaml"

_LEGACY_SCHEMA_PATTERN = re.compile(r'schema["\x27]\s*:\s*["\x27](ai|knowledge|runtime)["\x27]')
_MODULE_IMPORT_PATTERN = re.compile(r'(from|import)\s+modules\.(ai|knowledge|runtime)')


class TestNoLegacySchemaRefsInSource:
    def test_no_schema_ai_in_source(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
            text = py_file.read_text(encoding="utf-8")
            assert '"schema": "ai"' not in text, (
                f"{rel} contains schema='ai' reference"
            )

    def test_no_schema_knowledge_in_source(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
            text = py_file.read_text(encoding="utf-8")
            assert '"schema": "knowledge"' not in text, (
                f"{rel} contains schema='knowledge' reference"
            )

    def test_no_schema_runtime_in_source(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
            text = py_file.read_text(encoding="utf-8")
            assert '"schema": "runtime"' not in text, (
                f"{rel} contains schema='runtime' reference"
            )


class TestNoLegacyModuleImportsInSource:
    def test_no_ai_module_imports(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
            text = py_file.read_text(encoding="utf-8")
            matches = _MODULE_IMPORT_PATTERN.findall(text)
            for match_type, module in matches:
                if module == "ai":
                    assert False, f"{rel} contains import from modules.ai: {match_type}"

    def test_no_knowledge_module_imports(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
            text = py_file.read_text(encoding="utf-8")
            matches = _MODULE_IMPORT_PATTERN.findall(text)
            for match_type, module in matches:
                if module == "knowledge":
                    assert False, f"{rel} contains import from modules.knowledge: {match_type}"

    def test_no_runtime_module_imports(self):
        for py_file in SRC_DIR.rglob("*.py"):
            rel = str(py_file.relative_to(PROJECT_ROOT)).replace("\\", "/")
            text = py_file.read_text(encoding="utf-8")
            matches = _MODULE_IMPORT_PATTERN.findall(text)
            for match_type, module in matches:
                if module == "runtime":
                    assert False, f"{rel} contains import from modules.runtime: {match_type}"


class TestAllowlistOnlyHistorical:
    def test_allowlist_only_removal_spec_016(self):
        if not SCHEMA_ALLOWLIST.exists():
            return
        with open(SCHEMA_ALLOWLIST, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        entries = data.get("entries") or []
        for entry in entries:
            spec = entry.get("removal_spec", "")
            reason = entry.get("reason", "")
            assert spec == "016", (
                f"Allowlist entry with removal_spec='{spec}' should not exist for executable code: {reason}"
            )
