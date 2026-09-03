"""Workspace-wide architecture guards for bounded-context module boundaries."""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
SHARED = CORE_SRC / "shared"
API_PROCESS = PROJECT_ROOT / "packages" / "woobe-api" / "src"
WORKER_PROCESS = PROJECT_ROOT / "packages" / "woobe-workers" / "src"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = frozenset(
    path.name
    for path in SRC_MODULES.iterdir()
    if path.is_dir() and not path.name.startswith("_")
)


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _python_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _source_module(path: Path) -> str | None:
    try:
        relative = path.relative_to(SRC_MODULES)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None


def _absolute_import_from(path: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module

    try:
        relative = path.relative_to(CORE_SRC)
    except ValueError:
        return node.module

    package_parts = list(relative.with_suffix("").parts[:-1])
    ascend = max(node.level - 1, 0)
    if ascend > len(package_parts):
        return node.module
    base = package_parts[: len(package_parts) - ascend]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _literal_dynamic_import(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None

    if isinstance(node.func, ast.Name) and node.func.id == "__import__":
        return first.value
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "import_module"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
    ):
        return first.value
    return None


def _import_targets(path: Path) -> tuple[str, ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return ()

    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported = _absolute_import_from(path, node)
            if imported:
                targets.append(imported)
        elif isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            imported = _literal_dynamic_import(node)
            if imported:
                targets.append(imported)
    return tuple(targets)


def _cross_module_imports(path: Path) -> tuple[tuple[str, str], ...]:
    source_module = _source_module(path)
    if source_module is None:
        return ()
    values: list[tuple[str, str]] = []
    for imported in _import_targets(path):
        parts = imported.split(".")
        if (
            len(parts) >= 2
            and parts[0] == "modules"
            and parts[1] in KNOWN_MODULES
            and parts[1] != source_module
        ):
            values.append((parts[1], imported))
    return tuple(values)


def _allowlist_entries() -> list[dict]:
    if not ALLOWLIST_FILE.exists():
        return []
    with open(ALLOWLIST_FILE, encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    entries = data.get("entries") or []
    return list(entries) if isinstance(entries, list) else []


class TestGlobalModuleBoundaries:
    def test_every_core_bounded_context_is_auto_discovered(self):
        assert KNOWN_MODULES == frozenset(
            path.name
            for path in SRC_MODULES.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        )

    def test_bounded_contexts_do_not_import_other_bounded_contexts(self):
        violations = []
        for module_dir in sorted(SRC_MODULES.iterdir()):
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            for py_file in _python_files(module_dir):
                for target, imported in _cross_module_imports(py_file):
                    violations.append(
                        f"{_relative(py_file)} imports {target} via {imported}"
                    )
        assert not violations, (
            "Cross-bounded-context imports are forbidden. Compose through "
            "woobe-api/woobe-workers or an owning module port:\n"
            + "\n".join(violations[:80])
        )

    def test_shared_does_not_import_any_bounded_context(self):
        violations = []
        for py_file in _python_files(SHARED):
            for imported in _import_targets(py_file):
                parts = imported.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in KNOWN_MODULES:
                    violations.append(f"{_relative(py_file)} imports {imported}")
        assert not violations, (
            "shared must remain module-neutral:\n" + "\n".join(violations[:80])
        )

    def test_process_composition_roots_exist_outside_core(self):
        assert API_PROCESS.is_dir(), "packages/woobe-api/src must exist"
        assert WORKER_PROCESS.is_dir(), "packages/woobe-workers/src must exist"
        assert (WORKER_PROCESS / "worker_main.py").is_file()
        assert not (PROJECT_ROOT / "src" / "workers").exists()

    def test_concrete_workers_are_owned_by_worker_process(self):
        assert not list(SRC_MODULES.glob("*/infra/workers"))
        consumers = WORKER_PROCESS / "woobe_workers" / "consumers"
        assert consumers.is_dir()
        for module_name in ("agent", "core", "identity", "metering", "network", "observability"):
            assert (consumers / module_name / "registry.py").is_file()

    def test_module_boundary_allowlist_is_empty(self):
        entries = _allowlist_entries()
        assert not entries, (
            "Architecture allowlists are migration debt and must be empty at the "
            f"runtime-boundary DoD: {entries}"
        )


class TestGlobalModuleBoundariesRejectForbidden:
    def test_detects_static_cross_module_import(self, tmp_path: Path):
        module_dir = tmp_path / "modules" / "agent"
        module_dir.mkdir(parents=True)
        path = module_dir / "sample.py"
        path.write_text(
            "from modules.network.infra.database.models import NetworkModel\n",
            encoding="utf-8",
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module == "modules.network.infra.database.models"
            for node in ast.walk(tree)
        )

    def test_detects_dynamic_import_literals(self):
        tree = ast.parse(
            'import importlib\n'
            'a = importlib.import_module("modules.network.application.runtime")\n'
            'b = __import__("modules.agent.entrypoint")\n'
        )
        values = {
            value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            if (value := _literal_dynamic_import(node)) is not None
        }
        assert values == {
            "modules.network.application.runtime",
            "modules.agent.entrypoint",
        }

    def test_resolves_relative_imports_before_boundary_classification(self):
        path = SRC_MODULES / "agent" / "application" / "sample.py"
        node = ast.parse("from ...network.application import runtime\n").body[0]
        assert isinstance(node, ast.ImportFrom)
        assert _absolute_import_from(path, node) == "modules.network.application"
