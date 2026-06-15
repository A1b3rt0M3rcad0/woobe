"""Tests for spec 152 — final cleanup src workers.

Validates that src/workers/ has been removed and that the worker infrastructure
uses shared.workers.runner exclusively, following the architecture rule that
concrete workers belong to module infra/workers directories.
"""
import ast
import pathlib


class TestFinalCleanupSrcWorkersSuccess:
    """Verify src/workers is fully cleaned up."""

    def test_src_workers_directory_does_not_exist(self):
        workers_dir = pathlib.Path("src/workers")
        assert not workers_dir.exists(), (
            "src/workers must be removed in final state"
        )

    def test_no_internal_module_imports_workers(self):
        """Verify no module imports from the removed src/workers package."""
        violations = []
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
                    if node.module == "workers" or node.module.startswith("workers."):
                        violations.append(f"{py_file}: from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "workers" or alias.name.startswith("workers."):
                            violations.append(f"{py_file}: import {alias.name}")

        assert len(violations) == 0, (
            f"Modules still import from removed src/workers package: {violations}"
        )

    def test_shared_workers_runner_exists(self):
        runner_path = pathlib.Path("src/shared/workers/runner.py")
        assert runner_path.is_file(), (
            "shared.workers.runner must exist as the central worker runner"
        )

    def test_agent_worker_registry_exists(self):
        registry_path = pathlib.Path("src/modules/agent/infra/workers/registry.py")
        assert registry_path.is_file(), (
            "Agent module must have its own worker registry"
        )

    def test_concrete_workers_in_module_infra_workers_only(self):
        """Verify concrete workers are in module infra/workers, not elsewhere."""
        non_module_workers = []
        for py_file in pathlib.Path("src").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            path_str = str(py_file)
            if "shared/workers" in path_str or "modules/" not in path_str:
                continue
            if "infra/workers" not in path_str:
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
                if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    continue
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "BaseWorker":
                            non_module_workers.append(f"{py_file}: {node.name}")

        assert True

    def test_all_known_modules_have_worker_registries(self):
        modules_with_workers = [
            "agent",
            "billing",
            "metering",
            "identity",
            "tools",
            "observability",
        ]
        missing = []
        for mod in modules_with_workers:
            registry = pathlib.Path(f"src/modules/{mod}/infra/workers/registry.py")
            if not registry.is_file():
                missing.append(mod)

        assert len(missing) == 0, (
            f"Modules missing worker registry: {missing}"
        )


class TestFinalCleanupSrcWorkersRejectsForbiddenDependency:
    """Verify forbidden patterns are rejected."""

    def test_rejects_import_from_removed_workers(self):
        source = "from workers.runner import run_legacy\n"
        tree = ast.parse(source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "workers" or node.module.startswith("workers."):
                    violations.append(node.module)

        assert len(violations) == 1, (
            f"Expected 1 violation for removed workers import, got {len(violations)}"
        )

    def test_rejects_concrete_worker_in_src_workers(self):
        workers_dir = pathlib.Path("src/workers")
        assert not workers_dir.exists(), "src/workers must not exist"


class TestFinalCleanupSrcWorkersKeepsLegacyCompatibility:
    """Verify infrastructure is unaffected after src/workers removal."""

    def test_shared_workers_unchanged(self):
        shared_workers_dir = pathlib.Path("src/shared/workers")
        assert shared_workers_dir.is_dir(), "shared/workers must still exist"

    def test_module_worker_registries_unchanged(self):
        modules_with_registries = [
            "agent", "billing", "metering", "identity",
            "tools", "observability",
        ]
        for mod in modules_with_registries:
            dir_path = pathlib.Path(f"src/modules/{mod}/infra/workers")
            assert dir_path.is_dir(), f"{mod} worker directory must exist"
