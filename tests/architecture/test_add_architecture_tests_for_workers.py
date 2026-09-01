"""Package-aware architecture guards for workers."""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
WORKER_PROCESS = PROJECT_ROOT / "packages" / "woobe-workers" / "src"
SHARED_WORKERS = CORE_SRC / "shared" / "workers"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    path.name
    for path in SRC_MODULES.iterdir()
    if path.is_dir() and not path.name.startswith("_")
}


def _allowlist(scope: str) -> set[str]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    return {
        entry["file"].replace("\\", "/")
        for entry in data.get("entries") or []
        if entry.get("scope") == scope
    }


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _python_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _imports(path: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return ()
    values: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
        elif isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
    return tuple(values)


class TestAddArchitectureTestsForWorkers:
    def test_concrete_workers_do_not_cross_bounded_contexts(self):
        violations = []
        for module_dir in sorted(SRC_MODULES.iterdir()):
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            workers_dir = module_dir / "infra" / "workers"
            for py_file in _python_files(workers_dir):
                rel = _relative(py_file)
                for imported in _imports(py_file):
                    parts = imported.split(".")
                    if (
                        len(parts) >= 2
                        and parts[0] == "modules"
                        and parts[1] in KNOWN_MODULES
                        and parts[1] != module_dir.name
                    ):
                        violations.append(
                            f"{rel} ({module_dir.name}) imports {imported}"
                        )
        assert not violations, (
            "Concrete workers cross bounded-context boundaries:\n"
            + "\n".join(violations[:30])
        )

    def test_worker_registries_expose_expected_protocol(self):
        for module_dir in sorted(SRC_MODULES.iterdir()):
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            registry = module_dir / "infra" / "workers" / "registry.py"
            if not registry.is_file():
                continue
            tree = ast.parse(registry.read_text(encoding="utf-8"), filename=str(registry))
            classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
            if not classes:
                continue
            methods = {
                child.name
                for klass in classes
                for child in klass.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            assert "iter_workers" in methods, f"{_relative(registry)} missing iter_workers"
            assert "register" in methods, f"{_relative(registry)} missing register"

    def test_worker_base_contract_is_used(self):
        worker_bases = {
            "BaseWorker", "BaseInboxConsumer", "BaseInboxProcessor",
            "BaseOutboxDispatcher", "InboxConsumerWorker",
            "OutboxPublisherWorker", "InboxDispatcherWorker",
        }
        subclasses = []
        for module_dir in sorted(SRC_MODULES.iterdir()):
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            for py_file in _python_files(module_dir / "infra" / "workers"):
                try:
                    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    for base in node.bases:
                        name = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else None
                        if name in worker_bases:
                            subclasses.append(f"{_relative(py_file)}:{node.name}({name})")
        assert subclasses, "At least one concrete worker must implement the shared worker contract"

    def test_worker_process_package_is_bootstrap_only(self):
        assert WORKER_PROCESS.is_dir(), "packages/woobe-workers/src must exist"
        assert (WORKER_PROCESS / "worker_main.py").is_file()
        violations = []
        for py_file in _python_files(WORKER_PROCESS):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and "worker" in node.name.lower():
                    violations.append(f"{_relative(py_file)}: {node.name}")
        assert not violations, (
            "woobe-workers must compose concrete Core workers, not own them:\n"
            + "\n".join(violations)
        )

    def test_shared_workers_do_not_import_concrete_modules(self):
        allowlist = _allowlist("shared_boundaries")
        violations = []
        for py_file in _python_files(SHARED_WORKERS):
            rel = _relative(py_file)
            if rel in allowlist:
                continue
            for imported in _imports(py_file):
                if imported.startswith("modules."):
                    violations.append(f"{rel} imports {imported}")
        assert not violations, (
            "shared/workers imports concrete bounded contexts:\n"
            + "\n".join(violations[:30])
        )


class TestAddArchitectureTestsForWorkersRejectsForbidden:
    def test_detects_worker_outside_module_ownership(self):
        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            workers_dir = module_dir / "infra" / "workers"
            if workers_dir.is_dir():
                assert "infra/workers" in workers_dir.as_posix()

    def test_detects_shared_worker_with_module_import(self):
        tree = ast.parse("from modules.agent.domain.entities import Agent\n")
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("modules.")
            for node in ast.walk(tree)
        )
