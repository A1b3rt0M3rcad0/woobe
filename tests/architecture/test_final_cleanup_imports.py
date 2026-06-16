"""Tests for spec 150 — final cleanup imports.

Validates that no legacy module imports (modules.ai, modules.knowledge,
modules.runtime) remain in src/ or tests/ after the full migration to
modules.agent, and that the architecture boundary detection still works.
"""
import ast
import pathlib


LEGACY_MODULES = {"ai", "knowledge", "runtime"}


class TestFinalCleanupImportsSuccess:
    """Verify that all legacy module imports have been cleaned up."""

    def test_no_legacy_imports_in_src(self):
        active_imports = []
        for py_file in pathlib.Path("src").rglob("*.py"):
            if "__pycache__" in str(py_file):
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
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                        active_imports.append(f"{py_file}: from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                            active_imports.append(f"{py_file}: import {alias.name}")

        assert len(active_imports) == 0, (
            f"Legacy module imports still present in src/: {active_imports}"
        )

    def test_no_legacy_imports_in_tests(self):
        active_imports = []
        for py_file in pathlib.Path("tests").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            if py_file.name == "test_final_cleanup_imports.py":
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
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                        active_imports.append(f"{py_file}: from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                            active_imports.append(f"{py_file}: import {alias.name}")

        assert len(active_imports) == 0, (
            f"Legacy module imports still present in tests/: {active_imports}"
        )

    def test_legacy_module_directories_removed(self):
        ai_dir = pathlib.Path("src/modules/ai")
        knowledge_dir = pathlib.Path("src/modules/knowledge")
        runtime_dir = pathlib.Path("src/modules/runtime")

        assert not ai_dir.exists(), "src/modules/ai must be removed"
        assert not knowledge_dir.exists(), "src/modules/knowledge must be removed"
        assert not runtime_dir.exists(), "src/modules/runtime must be removed"

    def test_agent_module_is_the_target(self):
        agent_dir = pathlib.Path("src/modules/agent")
        assert agent_dir.is_dir(), "src/modules/agent must be the consolidated module"

    def test_no_legacy_allowlist_entries_remain(self):
        import yaml

        allowlist_path = pathlib.Path(
            "tests/architecture/legacy_import_allowlist.yaml"
        )
        if not allowlist_path.exists():
            return

        with open(allowlist_path, "r") as f:
            data = yaml.safe_load(f)

        entries = data.get("entries", [])
        legacy_entries = [
            e for e in entries
            if isinstance(e, dict)
            and any(
                f"modules.{m}" in str(e.get("file", ""))
                for m in LEGACY_MODULES
            )
        ]
        assert len(legacy_entries) == 0, (
            f"Legacy module allowlist entries still present: {legacy_entries}"
        )


class TestFinalCleanupImportsRejectsForbiddenDependency:
    """Verify the boundary detection still rejects forbidden patterns."""

    def test_rejects_legacy_module_import(self):
        forbidden_source = """\
from modules.ai.domain.entities import Agent
"""
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(node.module)

        assert len(violations) == 1, (
            f"Expected 1 legacy import violation, got {len(violations)}: {violations}"
        )
        assert "modules.ai.domain.entities" in violations

    def test_rejects_all_three_legacy_module_imports(self):
        forbidden_source = """\
from modules.ai.domain.entities import Agent
from modules.knowledge.infra.repositories import DocRepo
from modules.runtime.service.ask_use_case import AskAgentUseCase
"""
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(node.module)

        assert len(violations) == 3, (
            f"Expected 3 legacy import violations, got {len(violations)}: {violations}"
        )
        assert "modules.ai.domain.entities" in violations
        assert "modules.knowledge.infra.repositories" in violations
        assert "modules.runtime.service.ask_use_case" in violations

    def test_agent_module_boundaries_intact(self):
        source = """\
from modules.agent.domain.entities import Agent
from modules.agent.application.use_cases import SomeUseCase
"""
        tree = ast.parse(source)
        modules_imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "modules":
                    modules_imported.append(parts[1])

        assert all(m == "agent" for m in modules_imported), (
            f"Only agent module imports expected, got: {modules_imported}"
        )


class TestFinalCleanupImportsKeepsLegacyCompatibility:
    """Verify that no residual legacy shims remain."""

    def test_no_legacy_shims_exist(self):
        shim_files = [
            "src/modules/ai",
            "src/modules/knowledge",
            "src/modules/runtime",
        ]
        for shim_path in shim_files:
            assert not pathlib.Path(shim_path).exists(), (
                f"Legacy shim {shim_path} must not exist after final cleanup"
            )

    def test_other_modules_unaffected(self):
        other_modules = ["billing", "core", "identity", "metering", "observability", "tools"]
        for mod in other_modules:
            mod_dir = pathlib.Path(f"src/modules/{mod}")
            assert mod_dir.is_dir(), f"Non-legacy module src/modules/{mod} must still exist"

    def test_shared_module_unaffected(self):
        shared_dir = pathlib.Path("src/shared")
        assert shared_dir.is_dir(), "src/shared must still exist"
