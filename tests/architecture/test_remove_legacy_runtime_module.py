"""Tests for spec 145 — remove legacy runtime module.

Validates that the runtime bounded-context package remains removed, allowlist
entries are cleaned up, and no active references to modules.runtime remain in
production Python packages or tests.
"""
import ast
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "packages" / "woobe-core" / "src"
PRODUCTION_ROOTS = (
    CORE_SRC,
    ROOT / "packages" / "woobe-api" / "src",
    ROOT / "packages" / "woobe-workers" / "src",
)


class TestRemoveLegacyRuntimeModuleSuccess:
    """Verify the runtime module has been safely removed."""

    def test_runtime_module_directory_does_not_exist(self):
        runtime_dir = CORE_SRC / "modules" / "runtime"
        assert not runtime_dir.exists(), (
            "packages/woobe-core/src/modules/runtime must not exist"
        )

    def test_no_runtime_imports_in_production_or_tests(self):
        active_imports = []
        for base in (*PRODUCTION_ROOTS, ROOT / "tests"):
            if not base.is_dir():
                continue
            for py_file in base.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                if py_file.name == "test_remove_legacy_runtime_module.py":
                    continue
                try:
                    tree = ast.parse(
                        py_file.read_text(encoding="utf-8", errors="replace")
                    )
                except (OSError, SyntaxError):
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.module.startswith("modules.runtime"):
                            active_imports.append(
                                f"{py_file.relative_to(ROOT)}: from {node.module}"
                            )
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("modules.runtime"):
                                active_imports.append(
                                    f"{py_file.relative_to(ROOT)}: import {alias.name}"
                                )
        assert active_imports == [], (
            f"Active imports from modules.runtime found: {active_imports}"
        )

    def test_no_runtime_allowlist_entries_remain(self):
        import yaml

        allowlist_path = ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"
        with open(allowlist_path, encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}

        entries = data.get("entries", [])
        runtime_entries = [
            entry for entry in entries
            if isinstance(entry, dict)
            and "runtime" in str(entry.get("file", "")).lower()
        ]
        assert runtime_entries == [], (
            f"All runtime allowlist entries must be removed. Found: {runtime_entries}"
        )


class TestRemoveLegacyRuntimeModuleRejectsForbidden:
    """Verify no forbidden patterns remain after removal."""

    def test_no_orphaned_runtime_imports_in_agent_module(self):
        agent_dir = CORE_SRC / "modules" / "agent"
        for py_file in agent_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(encoding="utf-8", errors="replace")
            assert "modules.runtime" not in content, (
                f"{py_file.relative_to(ROOT)} should not reference modules.runtime"
            )

    def test_legacy_runtime_tests_removed(self):
        runtime_test_dir = ROOT / "tests" / "unit" / "test_runtime"
        assert not runtime_test_dir.exists(), (
            "Legacy runtime unit tests must be removed after module removal"
        )


class TestRemoveLegacyRuntimeModuleKeepsLegacyCompatibility:
    """Verify remaining Core infrastructure is unaffected."""

    def test_all_three_legacy_modules_are_removed(self):
        modules = CORE_SRC / "modules"
        for legacy in ("ai", "knowledge", "runtime"):
            assert not (modules / legacy).exists(), (
                f"Legacy module {legacy} must be removed"
            )

    def test_agent_module_still_exists(self):
        agent_dir = CORE_SRC / "modules" / "agent"
        assert agent_dir.is_dir(), "agent module must exist in woobe-core"
