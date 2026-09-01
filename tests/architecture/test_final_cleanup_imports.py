"""Tests for spec 150 — final cleanup imports.

Validates that no legacy module imports (modules.ai, modules.knowledge,
modules.runtime) remain in production Python package roots or tests after the
full migration to modules.agent, and that boundary detection still works.
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
LEGACY_MODULES = {"ai", "knowledge", "runtime"}


def _legacy_imports(base: pathlib.Path, *, excluded_file: str | None = None) -> list[str]:
    active_imports = []
    if not base.is_dir():
        return active_imports
    for py_file in base.rglob("*.py"):
        if "__pycache__" in str(py_file) or py_file.name == excluded_file:
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(content)
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    active_imports.append(f"{py_file.relative_to(ROOT)}: from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    parts = alias.name.split(".")
                    if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                        active_imports.append(f"{py_file.relative_to(ROOT)}: import {alias.name}")
    return active_imports


class TestFinalCleanupImportsSuccess:
    """Verify that all legacy module imports have been cleaned up."""

    def test_no_legacy_imports_in_production_packages(self):
        active_imports = []
        for source_root in PRODUCTION_ROOTS:
            active_imports.extend(_legacy_imports(source_root))
        assert active_imports == [], (
            f"Legacy module imports still present in production packages: {active_imports}"
        )

    def test_no_legacy_imports_in_tests(self):
        active_imports = _legacy_imports(
            ROOT / "tests", excluded_file="test_final_cleanup_imports.py"
        )
        assert active_imports == [], (
            f"Legacy module imports still present in tests/: {active_imports}"
        )

    def test_legacy_module_directories_removed(self):
        modules = CORE_SRC / "modules"
        for legacy in LEGACY_MODULES:
            assert not (modules / legacy).exists(), (
                f"packages/woobe-core/src/modules/{legacy} must be removed"
            )

    def test_agent_module_is_the_target(self):
        agent_dir = CORE_SRC / "modules" / "agent"
        assert agent_dir.is_dir(), (
            "packages/woobe-core/src/modules/agent must be the consolidated module"
        )

    def test_no_legacy_allowlist_entries_remain(self):
        import yaml

        allowlist_path = ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"
        if not allowlist_path.exists():
            return

        with open(allowlist_path, encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}

        entries = data.get("entries", [])
        legacy_entries = [
            entry for entry in entries
            if isinstance(entry, dict)
            and any(
                f"modules.{module}" in str(entry.get("file", ""))
                for module in LEGACY_MODULES
            )
        ]
        assert legacy_entries == [], (
            f"Legacy module allowlist entries still present: {legacy_entries}"
        )


class TestFinalCleanupImportsRejectsForbiddenDependency:
    """Verify the boundary detection still rejects forbidden patterns."""

    def test_rejects_legacy_module_import(self):
        forbidden_source = "from modules.ai.domain.entities import Agent\n"
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(node.module)

        assert violations == ["modules.ai.domain.entities"]

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
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
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

        assert all(module == "agent" for module in modules_imported), (
            f"Only agent module imports expected, got: {modules_imported}"
        )


class TestFinalCleanupImportsKeepsLegacyCompatibility:
    """Verify remaining Core infrastructure is unaffected."""

    def test_no_legacy_shims_exist(self):
        modules = CORE_SRC / "modules"
        for legacy in LEGACY_MODULES:
            assert not (modules / legacy).exists(), (
                f"Legacy shim {legacy} must not exist after final cleanup"
            )

    def test_other_modules_unaffected(self):
        other_modules = ["billing", "core", "identity", "metering", "observability"]
        for module in other_modules:
            mod_dir = CORE_SRC / "modules" / module
            assert mod_dir.is_dir(), (
                f"Non-legacy module packages/woobe-core/src/modules/{module} must still exist"
            )

    def test_shared_module_unaffected(self):
        shared_dir = CORE_SRC / "shared"
        assert shared_dir.is_dir(), "packages/woobe-core/src/shared must still exist"
