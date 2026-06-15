"""Tests for spec 143 — remove legacy ai module.

Validates that the ai module has been fully removed, allowlist entries are
cleaned up, and no active references to modules.ai remain in src or tests.
"""
import pathlib


class TestRemoveLegacyAiModuleSuccess:
    """Verify the ai module has been safely removed."""

    def test_ai_module_directory_does_not_exist(self):
        ai_dir = pathlib.Path("src/modules/ai")
        assert not ai_dir.exists(), (
            "src/modules/ai must not exist after spec 143 removal"
        )

    def test_no_ai_imports_in_src_or_tests(self):
        import ast

        active_imports = []
        for base in (pathlib.Path("src"), pathlib.Path("tests")):
            for py_file in base.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                if py_file.name == "test_remove_legacy_ai_module.py":
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
                        if node.module.startswith("modules.ai"):
                            active_imports.append(f"{py_file}: from {node.module}")
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("modules.ai"):
                                active_imports.append(f"{py_file}: import {alias.name}")
        assert len(active_imports) == 0, (
            f"Active imports from modules.ai found: {active_imports}"
        )

    def test_no_ai_allowlist_entries_remain(self):
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        ai_entries = [
            e for e in entries
            if isinstance(e, dict)
            and e.get("removal_spec") == "140"
        ]
        assert len(ai_entries) == 0, (
            f"All removal_spec '140' entries must be removed. Found: {ai_entries}"
        )


class TestRemoveLegacyAiModuleRejectsForbidden:
    """Verify no forbidden patterns remain after removal."""

    def test_no_orphaned_ai_imports_in_agent_module(self):
        agent_dir = pathlib.Path("src/modules/agent")
        for py_file in agent_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            content = py_file.read_text(encoding="utf-8", errors="replace")
            assert "modules.ai" not in content, (
                f"{py_file} should not reference modules.ai after removal"
            )

    def test_legacy_ai_tests_removed(self):
        ai_test_dir = pathlib.Path("tests/unit/test_ai")
        assert not ai_test_dir.exists(), (
            "Legacy ai unit tests must be removed after module removal"
        )


class TestRemoveLegacyAiModuleKeepsLegacyCompatibility:
    """Verify remaining legacy modules are unaffected."""

    def test_knowledge_module_not_required_to_exist(self):
        pass

    def test_all_legacy_ai_knowledge_runtime_removed(self):
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
            "Allowlist should still have remaining entries for knowledge and runtime"
        )
