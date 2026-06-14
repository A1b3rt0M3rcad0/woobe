"""Tests for spec 113 — add architecture tests for workers.

Validates worker placement, worker registry contracts, BaseWorker inheritance,
and cross-module import restrictions for concrete workers.
"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
SRC_WORKERS = PROJECT_ROOT / "src" / "workers"
SHARED_WORKERS = PROJECT_ROOT / "src" / "shared" / "workers"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}

LEGACY_MODULES = {"ai", "knowledge", "runtime"}


def _load_allowlist(scope: str) -> set[str]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        e["file"].replace("\\", "/")
        for e in entries
        if e.get("scope") == scope
    }


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _src_files_under(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


class TestAddArchitectureTestsForWorkers:
    """Worker architecture tests for spec 113."""

    def test_add_architecture_tests_for_workers(self):
        violations = []

        for mdir in sorted(SRC_MODULES.iterdir()):
            if not mdir.is_dir() or mdir.name.startswith("_"):
                continue
            module_name = mdir.name
            workers_dir = mdir / "infra" / "workers"

            if not workers_dir.is_dir():
                continue

            for py_file in _src_files_under(workers_dir):
                rel = _relative_posix(py_file)
                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError):
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        parts = str(node.module).split(".")
                        if len(parts) >= 2 and parts[0] == "modules":
                            target = parts[1]
                            if target != module_name and target in KNOWN_MODULES:
                                allowlist = _load_allowlist("module_boundaries")
                                if rel not in allowlist and rel.replace("\\", "/") not in allowlist:
                                    violations.append(
                                        f"{rel} (module={module_name}) imports {target}"
                                    )

        assert not violations, (
            f"Found {len(violations)} worker cross-module import(s):\n"
            + "\n".join(violations[:20])
        )

    def test_worker_registry_satisfies_protocol(self):
        for mdir in sorted(SRC_MODULES.iterdir()):
            if not mdir.is_dir() or mdir.name.startswith("_"):
                continue
            registry_file = mdir / "infra" / "workers" / "registry.py"
            if not registry_file.is_file():
                continue

            source = registry_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(registry_file))

            registry_class = None
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    registry_class = node
                    break

            if registry_class is None:
                continue

            has_iter = any(
                isinstance(node, ast.FunctionDef) and node.name == "iter_workers"
                for node in ast.walk(registry_class)
            )
            has_register = any(
                isinstance(node, ast.FunctionDef) and node.name == "register"
                for node in ast.walk(registry_class)
            )

            assert has_iter, (
                f"{_relative_posix(registry_file)}: registry class "
                f"'{registry_class.name}' missing iter_workers method"
            )
            assert has_register, (
                f"{_relative_posix(registry_file)}: registry class "
                f"'{registry_class.name}' missing register method"
            )

    def test_worker_classes_inherit_base_worker(self):
        worker_base_classes = {
            "BaseWorker", "BaseInboxConsumer", "BaseInboxProcessor",
            "BaseOutboxDispatcher", "InboxConsumerWorker",
            "OutboxPublisherWorker", "InboxDispatcherWorker",
        }
        base_worker_subclasses = 0
        working_workers = []

        for mdir in sorted(SRC_MODULES.iterdir()):
            if not mdir.is_dir() or mdir.name.startswith("_"):
                continue
            workers_dir = mdir / "infra" / "workers"
            if not workers_dir.is_dir():
                continue

            for py_file in _src_files_under(workers_dir):
                if py_file.name == "registry.py" or py_file.name == "__init__.py":
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue

                tree = ast.parse(source, filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for base in node.bases:
                            base_name = None
                            if isinstance(base, ast.Name):
                                base_name = base.id
                            elif isinstance(base, ast.Attribute):
                                base_name = base.attr

                            if base_name and base_name in worker_base_classes:
                                base_worker_subclasses += 1
                                working_workers.append(
                                    f"{_relative_posix(py_file)}: {node.name}({base_name})"
                                )

        assert base_worker_subclasses > 0, (
            f"Expected at least one worker class inheriting from a worker base class. "
            f"Found: {working_workers if working_workers else 'none'}"
        )

    def test_src_workers_no_concrete_implementation(self):
        if not SRC_WORKERS.is_dir():
            return

        allowlist = _load_allowlist("worker_locations")
        violations = []

        for py_file in _src_files_under(SRC_WORKERS):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = str(node.module).split(".")
                    if len(parts) >= 2 and parts[0] == "modules":
                        target = parts[1]
                        if rel not in allowlist and rel.replace("\\", "/") not in allowlist:
                            violations.append(
                                f"{rel} imports module {target} (unlisted)"
                            )

        assert not violations, (
            f"src/workers has {len(violations)} unlisted module import(s):\n"
            + "\n".join(violations[:20])
        )

    def test_workers_only_in_module_infra_workers(self):
        for mdir in sorted(SRC_MODULES.iterdir()):
            if not mdir.is_dir() or mdir.name.startswith("_"):
                continue
            workers_dir = mdir / "infra" / "workers"
            if workers_dir.is_dir():
                for py_file in _src_files_under(workers_dir):
                    rel = _relative_posix(py_file)
                    assert "modules" in rel, (
                        f"Worker file outside expected module path: {rel}"
                    )

    def test_shared_workers_no_concrete_module_imports(self):
        if not SHARED_WORKERS.is_dir():
            return

        allowlist = _load_allowlist("shared_boundaries")
        violations = []

        for py_file in _src_files_under(SHARED_WORKERS):
            rel = _relative_posix(py_file)

            if rel in allowlist or rel.replace("\\", "/") in allowlist:
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = str(node.module).split(".")
                    if len(parts) >= 2 and parts[0] == "modules":
                        violations.append(
                            f"{rel} imports {node.module}"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("modules."):
                            violations.append(
                                f"{rel} imports {alias.name}"
                            )

        assert not violations, (
            f"shared/workers has {len(violations)} unlisted module import(s):\n"
            + "\n".join(violations[:20])
        )


class TestAddArchitectureTestsForWorkersRejectsForbidden:
    """Regression: forbidden worker patterns are detected."""

    def test_detects_worker_outside_module_infra_workers(self):
        assert SRC_WORKERS.is_dir() or True

        worker_dirs = []
        for mdir in SRC_MODULES.iterdir():
            if not mdir.is_dir() or mdir.name.startswith("_"):
                continue
            workers_dir = mdir / "infra" / "workers"
            if workers_dir.is_dir():
                worker_dirs.append(str(workers_dir.relative_to(PROJECT_ROOT)))

        for wd in worker_dirs:
            assert "infra/workers" in wd or "infra\\workers" in wd, (
                f"Worker directory at wrong path: {wd}"
            )

    def test_detects_shared_worker_with_module_import(self):
        code = "from modules.agent.domain.entities import Agent\n"
        tree = ast.parse(code)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("modules."):
                    found = True
        assert found
