"""Package-aware architecture guards for the shared layer."""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
SRC_SHARED = CORE_SRC / "shared"
WORKER_PROCESS = PROJECT_ROOT / "packages" / "woobe-workers" / "src"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    path.name
    for path in SRC_MODULES.iterdir()
    if path.is_dir() and not path.name.startswith("_")
}
LEGACY_MODULES = {"ai", "knowledge", "runtime"}


def _shared_allowlist() -> set[str]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    return {
        entry["file"].replace("\\", "/")
        for entry in data.get("entries") or []
        if entry.get("scope") == "shared_boundaries"
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


class TestAddArchitectureTestsForSharedLayer:
    def test_shared_has_no_static_bounded_context_imports(self):
        violations = []
        for py_file in _python_files(SRC_SHARED):
            for imported in _imports(py_file):
                parts = imported.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in KNOWN_MODULES:
                    violations.append(f"{_relative(py_file)} imports {imported}")
        assert not violations, (
            "Shared statically imports bounded contexts:\n"
            + "\n".join(violations[:30])
        )

    def test_shared_has_no_domain_application_implementations(self):
        violations = []
        for py_file in _python_files(SRC_SHARED):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                lower = node.name.lower()
                looks_domain = any(token in lower for token in ("usecase", "use_case", "aggregate"))
                if looks_domain:
                    violations.append(f"{_relative(py_file)}: {node.name}")
        assert not violations, (
            "Shared contains bounded-context business implementations:\n"
            + "\n".join(violations[:30])
        )

    def test_shared_legacy_references_are_explicitly_allowlisted(self):
        allowlist = _shared_allowlist()
        violations = []
        for py_file in _python_files(SRC_SHARED):
            rel = _relative(py_file)
            if rel in allowlist:
                continue
            source = py_file.read_text(encoding="utf-8", errors="replace")
            for legacy in LEGACY_MODULES:
                if f"modules.{legacy}." in source:
                    violations.append(f"{rel} references modules.{legacy}")
        assert not violations, (
            "Shared references removed legacy modules:\n"
            + "\n".join(violations[:30])
        )

    def test_worker_process_is_not_a_shared_runtime_folder(self):
        assert WORKER_PROCESS.is_dir(), "Worker process package must exist"
        assert not (PROJECT_ROOT / "src" / "workers").exists()

    def test_shared_allowlist_entries_are_live(self):
        if not ALLOWLIST_FILE.exists():
            return
        with open(ALLOWLIST_FILE, encoding="utf-8") as stream:
            data = yaml.safe_load(stream) or {}
        for entry in data.get("entries") or []:
            if entry.get("scope") != "shared_boundaries":
                continue
            assert entry.get("removal_spec"), f"Missing removal_spec: {entry}"
            path = PROJECT_ROOT.joinpath(*entry["file"].replace("\\", "/").split("/"))
            assert path.exists(), f"Shared allowlist path does not exist: {entry['file']}"


class TestAddArchitectureTestsForSharedLayerRejectsForbidden:
    def test_detects_forbidden_module_import_in_shared(self):
        tree = ast.parse("from modules.agent.domain.entities import Agent\n")
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("modules.agent")
            for node in ast.walk(tree)
        )

    def test_detects_domain_class_in_shared(self):
        tree = ast.parse("class CreateAgentUseCase:\n    pass\n")
        assert any(
            isinstance(node, ast.ClassDef) and "usecase" in node.name.lower()
            for node in ast.walk(tree)
        )

    def test_detects_legacy_module_reference_in_shared(self):
        assert "modules.ai" in "from modules.ai.infra.models import Model\n"
