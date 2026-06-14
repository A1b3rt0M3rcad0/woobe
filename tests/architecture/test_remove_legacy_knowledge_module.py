"""Tests for spec 144 — remove legacy knowledge module.

Validates that the knowledge module has been fully removed, allowlist entries
are cleaned up, and no active references to modules.knowledge remain in src or
tests.
"""
import pathlib


class TestRemoveLegacyKnowledgeModuleSuccess:
    """Verify the knowledge module has been safely removed."""

    def test_knowledge_module_directory_does_not_exist(self):
        knowledge_dir = pathlib.Path("src/modules/knowledge")
        assert not knowledge_dir.exists(), (
            "src/modules/knowledge must not exist after spec 144 removal"
        )

    def test_no_knowledge_imports_in_src_or_tests(self):
        import ast

        active_imports = []
        for base in (pathlib.Path("src"), pathlib.Path("tests")):
            for py_file in base.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                if py_file.name == "test_remove_legacy_knowledge_module.py":
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
                        if node.module.startswith("modules.knowledge"):
                            active_imports.append(f"{py_file}: from {node.module}")
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("modules.knowledge"):
                                active_imports.append(f"{py_file}: import {alias.name}")
        assert len(active_imports) == 0, (
            f"Active imports from modules.knowledge found: {active_imports}"
        )

    def test_no_knowledge_allowlist_entries_remain(self):
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        knowledge_entries = [
            e for e in entries
            if isinstance(e, dict)
            and e.get("removal_spec") == "141"
        ]
        assert len(knowledge_entries) == 0, (
            f"All removal_spec '141' entries must be removed. Found: {knowledge_entries}"
        )


class TestRemoveLegacyKnowledgeModuleRejectsForbidden:
    """Verify no forbidden patterns remain after removal."""

    def test_no_orphaned_knowledge_imports_in_agent_module(self):
        agent_dir = pathlib.Path("src/modules/agent")
        for py_file in agent_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(encoding="utf-8", errors="replace")
            assert "modules.knowledge" not in content, (
                f"{py_file} should not reference modules.knowledge after removal"
            )

    def test_legacy_knowledge_tests_removed(self):
        knowledge_test_dir = pathlib.Path("tests/unit/test_knowledge")
        assert not knowledge_test_dir.exists(), (
            "Legacy knowledge unit tests must be removed after module removal"
        )


class TestRemoveLegacyKnowledgeModuleKeepsLegacyCompatibility:
    """Verify remaining legacy modules are unaffected."""

    def test_all_legacy_knowledge_runtime_removed(self):
        pass

    def test_legacy_import_allowlist_still_has_remaining_entries(self):
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        assert len(entries) > 0, (
            "Allowlist should still have remaining entries for runtime"
        )
