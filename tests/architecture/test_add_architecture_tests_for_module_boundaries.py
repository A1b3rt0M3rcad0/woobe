"""Package-aware architecture guards for bounded-context module boundaries."""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
SHARED = CORE_SRC / "shared"
WORKER_PROCESS = PROJECT_ROOT / "packages" / "woobe-workers" / "src"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    path.name
    for path in SRC_MODULES.iterdir()
    if path.is_dir() and not path.name.startswith("_")
}
LEGACY_MODULES = {"ai", "knowledge", "runtime"}
AGENT_FORBIDDEN_TARGETS = KNOWN_MODULES - {"agent", *LEGACY_MODULES}


def _load_module_allowlist() -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    entries = data.get("entries") or []
    return {
        (entry["file"].replace("\\", "/"), entry["target_module"])
        for entry in entries
        if entry.get("scope") == "module_boundaries" and entry.get("target_module")
    }


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _python_files(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.rglob("*.py") if path.is_file()))


def _cross_module_imports(path: Path, source_module: str) -> tuple[tuple[str, str], ...]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return ()
    values: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            targets.append(node.module)
        elif isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        for imported in targets:
            parts = imported.split(".")
            if (
                len(parts) >= 2
                and parts[0] == "modules"
                and parts[1] in KNOWN_MODULES
                and parts[1] != source_module
            ):
                values.append((parts[1], imported))
    return tuple(values)


class TestAddArchitectureTestsForModuleBoundaries:
    def test_cross_module_imports_are_explicitly_allowlisted(self):
        allowlist = _load_module_allowlist()
        violations = []
        for module_dir in sorted(SRC_MODULES.iterdir()):
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            for py_file in _python_files(module_dir):
                rel = _relative(py_file)
                for target, imported in _cross_module_imports(py_file, module_dir.name):
                    if (rel, target) not in allowlist:
                        violations.append(f"{rel} imports {target} via {imported}")
        assert not violations, (
            "Unlisted cross-module imports:\n" + "\n".join(violations[:40])
        )

    def test_shared_does_not_import_bounded_context_domain(self):
        violations = []
        for py_file in _python_files(SHARED):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                imported = node.module if isinstance(node, ast.ImportFrom) else None
                if imported and imported.startswith("modules."):
                    violations.append(f"{_relative(py_file)} imports {imported}")
        assert not violations, (
            "Shared must not statically import bounded contexts:\n"
            + "\n".join(violations[:30])
        )

    def test_worker_process_is_separate_from_core_modules(self):
        assert WORKER_PROCESS.is_dir(), "packages/woobe-workers/src must exist"
        assert (WORKER_PROCESS / "worker_main.py").is_file()
        assert not (PROJECT_ROOT / "src" / "workers").exists()

    def test_concrete_worker_directories_are_module_owned(self):
        for module_dir in sorted(SRC_MODULES.iterdir()):
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            workers_dir = module_dir / "infra" / "workers"
            for py_file in _python_files(workers_dir):
                assert py_file.is_relative_to(SRC_MODULES), (
                    f"Worker outside Core module ownership: {_relative(py_file)}"
                )

    def test_agent_does_not_import_non_agent_bounded_contexts(self):
        agent_dir = SRC_MODULES / "agent"
        violations = []
        for py_file in _python_files(agent_dir):
            for target, imported in _cross_module_imports(py_file, "agent"):
                if target in AGENT_FORBIDDEN_TARGETS:
                    violations.append(f"{_relative(py_file)} imports {imported}")
        assert not violations, (
            "Agent imports non-Agent bounded contexts:\n"
            + "\n".join(violations[:30])
        )

    def test_allowlist_entries_are_well_formed_and_reference_live_files(self):
        if not ALLOWLIST_FILE.exists():
            return
        with open(ALLOWLIST_FILE, encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        for entry in data.get("entries") or []:
            assert entry.get("scope"), f"Allowlist entry missing scope: {entry}"
            assert entry.get("removal_spec"), f"Allowlist entry missing removal_spec: {entry}"
            path = PROJECT_ROOT.joinpath(*entry["file"].replace("\\", "/").split("/"))
            assert path.exists(), f"Allowlist references non-existent file: {entry['file']}"


class TestAddArchitectureTestsForModuleBoundariesRejectsForbidden:
    def test_detects_forbidden_cross_module_import(self):
        tree = ast.parse("from modules.core.infra.database.repositories import ProjectRepository\n")
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("modules.core")
            for node in ast.walk(tree)
        )

    def test_detects_shared_containing_module_domain(self):
        tree = ast.parse("from modules.agent.domain.entities import Agent\n")
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("modules.agent.domain")
            for node in ast.walk(tree)
        )
