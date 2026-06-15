"""Tests for spec 145 — remove legacy runtime module.

Validates that the runtime module has been fully removed, allowlist entries
are cleaned up, and no active references to modules.runtime remain in src or
tests.
"""
import pathlib


class TestRemoveLegacyRuntimeModuleSuccess:
    """Verify the runtime module has been safely removed."""

    def test_runtime_module_directory_does_not_exist(self):
        runtime_dir = pathlib.Path("src/modules/runtime")
        assert not runtime_dir.exists(), (
            "src/modules/runtime must not exist after spec 145 removal"
        )

    def test_no_runtime_imports_in_src_or_tests(self):
        import ast

        active_imports = []
        for base in (pathlib.Path("src"), pathlib.Path("tests")):
            for py_file in base.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                if py_file.name == "test_remove_legacy_runtime_module.py":
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        if node.module.startswith("modules.runtime"):
                            active_imports.append(f"{py_file}: from {node.module}")
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("modules.runtime"):
                                active_imports.append(f"{py_file}: import {alias.name}")
        assert len(active_imports) == 0, (
            f"Active imports from modules.runtime found: {active_imports}"
        )

    def test_no_runtime_allowlist_entries_remain(self):
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        runtime_entries = [
            e for e in entries
            if isinstance(e, dict)
            and "runtime" in str(e.get("file", "")).lower()
        ]
        assert len(runtime_entries) == 0, (
            f"All runtime allowlist entries must be removed. Found: {runtime_entries}"
        )


class TestRemoveLegacyRuntimeModuleRejectsForbidden:
    """Verify no forbidden patterns remain after removal."""

    def test_no_orphaned_runtime_imports_in_agent_module(self):
        agent_dir = pathlib.Path("src/modules/agent")
        for py_file in agent_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(encoding="utf-8", errors="replace")
            assert "modules.runtime" not in content, (
                f"{py_file} should not reference modules.runtime after removal"
            )

    def test_legacy_runtime_tests_removed(self):
        runtime_test_dir = pathlib.Path("tests/unit/test_runtime")
        assert not runtime_test_dir.exists(), (
            "Legacy runtime unit tests must be removed after module removal"
        )


class TestRemoveLegacyRuntimeModuleKeepsLegacyCompatibility:
    """Verify remaining infrastructure is unaffected."""

    def test_all_three_legacy_modules_are_removed(self):
        ai_dir = pathlib.Path("src/modules/ai")
        knowledge_dir = pathlib.Path("src/modules/knowledge")
        runtime_dir = pathlib.Path("src/modules/runtime")
        assert not ai_dir.exists(), "ai module must be removed"
        assert not knowledge_dir.exists(), "knowledge module must be removed"
        assert not runtime_dir.exists(), "runtime module must be removed"

    def test_agent_module_still_exists(self):
        agent_dir = pathlib.Path("src/modules/agent")
        assert agent_dir.is_dir(), "agent module must exist"
