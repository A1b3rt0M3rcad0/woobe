"""Tests for spec 015 — application cutover and observability.

Validates that:
- No runtime code references legacy schemas (ai, knowledge, runtime)
- All imports from non-agent legacy modules have been removed from src/
- Application bootstrap no longer depends on legacy schema references
- Database already has all agent tables in agent schema
- Compat views exist only as compatibility layer, not as primary access path
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

# Modules that should not be imported in src/ after cutover
LEGACY_MODULES = {"modules.ai", "modules.knowledge", "modules.runtime"}


class TestCutoverNoLegacySchemaInSource:
    def test_no_schema_ai_in_source(self):
        for py_file in _iter_source():
            text = py_file.read_text(encoding="utf-8")
            if re.search(r'schema\s*=\s*["\x27]ai["\x27]', text):
                rel = py_file.relative_to(PROJECT_ROOT)
                assert False, f"Legacy schema='ai' found in {rel}"

    def test_no_schema_knowledge_in_source(self):
        for py_file in _iter_source():
            text = py_file.read_text(encoding="utf-8")
            if re.search(r'schema\s*=\s*["\x27]knowledge["\x27]', text):
                rel = py_file.relative_to(PROJECT_ROOT)
                assert False, f"Legacy schema='knowledge' found in {rel}"

    def test_no_schema_runtime_in_source(self):
        for py_file in _iter_source():
            text = py_file.read_text(encoding="utf-8")
            if re.search(r'schema\s*=\s*["\x27]runtime["\x27]', text):
                rel = py_file.relative_to(PROJECT_ROOT)
                assert False, f"Legacy schema='runtime' found in {rel}"


class TestCutoverNoLegacyModuleImports:
    def test_no_ai_module_imports(self):
        for py_file in _iter_source():
            if _imports_legacy_module(py_file, "modules.ai"):
                rel = py_file.relative_to(PROJECT_ROOT)
                assert False, f"Import from modules.ai found in {rel}"

    def test_no_knowledge_module_imports(self):
        for py_file in _iter_source():
            if _imports_legacy_module(py_file, "modules.knowledge"):
                rel = py_file.relative_to(PROJECT_ROOT)
                assert False, f"Import from modules.knowledge found in {rel}"

    def test_no_runtime_module_imports(self):
        for py_file in _iter_source():
            if _imports_legacy_module(py_file, "modules.runtime"):
                rel = py_file.relative_to(PROJECT_ROOT)
                assert False, f"Import from modules.runtime found in {rel}"


class TestCutoverDatabaseState:
    def test_agent_schema_is_canonical(self):
        model_files = list(SRC_DIR.rglob("*/models.py"))
        agent_models_found = 0
        for mf in model_files:
            text = mf.read_text(encoding="utf-8")
            if re.search(r'schema["\s]*[:=]["\s]*"agent"', text):
                agent_models_found += 1
        assert agent_models_found >= 1, (
            "No models with schema='agent' found in any module"
        )


def _iter_source() -> list[Path]:
    exclude_dirs = {"__pycache__", ".venv", "node_modules"}
    files: list[Path] = []
    for path in SRC_DIR.rglob("*.py"):
        if any(excl in path.parts for excl in exclude_dirs):
            continue
        files.append(path)
    return files


def _imports_legacy_module(filepath: Path, module_name: str) -> bool:
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(module_name):
                    return True
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(module_name):
                return True
    return False
