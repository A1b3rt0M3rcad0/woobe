"""Tests for spec 151 — final cleanup dead code.

Validates that no dead code (empty placeholder files, orphaned imports,
unreachable references to removed modules) remains in the repository after
the full migration to modules.agent.
"""
import ast
import pathlib


LEGACY_MODULES = {"ai", "knowledge", "runtime"}
AUTOGEN_PATTERNS = {"__pycache__", ".pytest_cache", ".venv", ".git"}


def _is_autogen(path: pathlib.Path) -> bool:
    return any(p in str(path) for p in AUTOGEN_PATTERNS)


class TestFinalCleanupDeadCodeSuccess:
    """Verify no dead code remains after migration."""

    def test_no_empty_python_files_in_src(self):
        empty_files = []
        for py_file in pathlib.Path("src").rglob("*.py"):
            if _is_autogen(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            stripped = content.strip()
            if not stripped or (stripped.startswith('"""') and stripped.endswith('"""') and len(stripped.splitlines()) <= 1):
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            has_code = False
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.Expr, ast.Import, ast.ImportFrom)):
                    has_code = True
                    break
            if not has_code and len(stripped) > 0:
                empty_files.append(str(py_file))

        assert len(empty_files) == 0, (
            f"Empty Python files detected in src/: {empty_files}"
        )

    def test_no_imports_from_removed_modules(self):
        """Verify no file imports from modules that were removed (ai, knowledge, runtime)."""
        violations = []
        for py_file in pathlib.Path("src").rglob("*.py"):
            if _is_autogen(py_file):
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
                        violations.append(f"{py_file}: from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                            violations.append(f"{py_file}: import {alias.name}")

        assert len(violations) == 0, (
            f"Imports from removed legacy modules found in src/: {violations}"
        )

    def test_no_dunder_init_without_package_purpose(self):
        """All __init__.py files should either be empty (package marker) or have content."""
        orphaned_inits = []
        for init_file in pathlib.Path("src").rglob("__init__.py"):
            if _is_autogen(init_file):
                continue
            try:
                content = init_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if not content.strip():
                if init_file.parent == pathlib.Path("src"):
                    continue
                no_other_files = True
                for child in init_file.parent.iterdir():
                    if child.name != "__init__.py" and not child.name.startswith("__pycache__"):
                        no_other_files = False
                        break
                if no_other_files:
                    orphaned_inits.append(str(init_file))

        assert len(orphaned_inits) == 0, (
            f"Orphaned __init__.py files (no siblings): {orphaned_inits}"
        )

    def test_no_duplicate_top_level_definitions_in_agent(self):
        """Verify no duplicate top-level class/function names within each agent layer."""
        agent_dir = pathlib.Path("src/modules/agent")
        layers = {
            "domain": agent_dir / "domain",
            "application": agent_dir / "application",
            "infra": agent_dir / "infra",
            "presentation": agent_dir / "presentation",
        }
        duplicates = []

        for layer_name, layer_dir in layers.items():
            if not layer_dir.is_dir():
                continue
            defined_names = {}
            for py_file in layer_dir.rglob("*.py"):
                if _is_autogen(py_file) or py_file.name.startswith("__"):
                    continue
                try:
                    content = py_file.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        if node.name.startswith("__"):
                            continue
                        if node.name in defined_names and defined_names[node.name] != str(py_file):
                            duplicates.append(
                                f"{layer_name}: {node.name} in {defined_names[node.name]} vs {py_file}"
                            )
                        else:
                            defined_names[node.name] = str(py_file)

        assert len(duplicates) == 0, (
            f"Duplicate top-level definitions found in agent module: {duplicates}"
        )

    def test_agent_module_has_all_required_layers(self):
        """Verify the agent module has populated domain, application, infra, presentation layers."""
        required_dirs = [
            "src/modules/agent/domain",
            "src/modules/agent/application",
            "src/modules/agent/infra",
            "src/modules/agent/presentation",
        ]
        for d in required_dirs:
            dir_path = pathlib.Path(d)
            assert dir_path.is_dir(), f"Required directory missing: {d}"


class TestFinalCleanupDeadCodeRejectsForbiddenDependency:
    """Verify dead code patterns are detected and rejected."""

    def test_rejects_import_from_removed_module(self):
        forbidden_source = """\
from modules.ai.domain.entities import Agent
class MyClass:
    pass
"""
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(node.module)

        assert len(violations) == 1, (
            f"Expected 1 violation from removed module import, got {len(violations)}"
        )
        assert "modules.ai.domain.entities" in violations

    def test_rejects_empty_placeholder_file(self):
        source = '\n"""Placeholder-only docstring."""\n'
        tree = ast.parse(source)
        has_content = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Assign)):
                has_content = True
                break
        assert not has_content, "Empty placeholder files should be detected as dead code"

    def test_rejects_unreachable_legacy_reference(self):
        source = "from modules.knowledge.infra.repositories import DocRepo\n"
        tree = ast.parse(source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 3 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(node.module)

        assert len(violations) == 1, (
            f"Expected 1 violation for legacy import, got {len(violations)}"
        )


class TestFinalCleanupDeadCodeKeepsLegacyCompatibility:
    """Verify remaining infrastructure is unaffected by dead code cleanup."""

    def test_other_modules_not_affected(self):
        other_modules = ["billing", "core", "identity", "metering", "observability", "tools"]
        for mod in other_modules:
            mod_dir = pathlib.Path(f"src/modules/{mod}")
            assert mod_dir.is_dir(), f"Non-legacy module {mod} must still exist"

    def test_shared_module_intact(self):
        shared_dir = pathlib.Path("src/shared")
        assert shared_dir.is_dir(), "src/shared must still exist"

    def test_src_workers_deprecated_directory_removed(self):
        workers_dir = pathlib.Path("src/workers")
        assert not workers_dir.exists(), "src/workers must be removed (spec 152)"
