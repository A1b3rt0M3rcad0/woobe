"""Tests for spec 111 — add architecture tests for module boundaries.

Validates module import boundaries, shared-layer isolation, worker placement,
and agent external module import restrictions. Uses the legacy import allowlist
for temporary cross-module entries during migration.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
SRC_WORKERS = PROJECT_ROOT / "src" / "workers"
SHARED = PROJECT_ROOT / "src" / "shared"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}

LEGACY_MODULES = {"ai", "knowledge", "runtime"}

AGENT_FORBIDDEN_TARGETS = KNOWN_MODULES - {"agent", *LEGACY_MODULES}


def _load_allowlist(scope: str) -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (e["file"].replace("\\", "/"), e["target_module"])
        for e in entries
        if e.get("scope") == scope
    }


def _extract_cross_module_imports(
    file_path: Path, source_module: str
) -> list[tuple[str, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if len(parts) >= 2 and parts[0] == "modules":
                target_module = parts[1]
                if target_module != source_module and target_module in KNOWN_MODULES:
                    violations.append((target_module, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) >= 2 and parts[0] == "modules":
                    target_module = parts[1]
                    if target_module != source_module and target_module in KNOWN_MODULES:
                        violations.append((target_module, alias.name))
    return violations


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _repository_path(path_value: str) -> Path:
    return PROJECT_ROOT.joinpath(*path_value.replace("\\", "/").split("/"))


def _src_files_under(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


class TestAddArchitectureTestsForModuleBoundaries:
    """Module boundary architecture tests for spec 111."""

    def test_add_architecture_tests_for_module_boundaries(self):
        allowlist = _load_allowlist("module_boundaries")
        unlisted = []

        for mdir in sorted(SRC_MODULES.iterdir()):
            if not mdir.is_dir() or mdir.name.startswith("_"):
                continue
            module_name = mdir.name
            for py_file in _src_files_under(mdir):
                rel = _relative_posix(py_file)
                violations = _extract_cross_module_imports(py_file, module_name)
                for target_module, import_path in violations:
                    if (rel, target_module) not in allowlist and (
                        rel.replace("\\", "/"),
                        target_module,
                    ) not in allowlist:
                        unlisted.append(
                            f"{rel} imports {target_module} ({import_path})"
                        )

        unlisted.sort()
        assert not unlisted, (
            f"Found {len(unlisted)} unlisted cross-module import(s):\n"
            + "\n".join(unlisted)
        )

    def test_no_domain_in_shared(self):
        domain_patterns = [
            "domain.entities",
            "domain.value_objects",
            "domain.enums",
            "domain.errors",
            "application.use_cases",
            "application.dtos",
            "domain.repositories",
            "domain.services",
            "service.use_cases",
            "service.dtos",
            "domain.events",
        ]

        for py_file in _src_files_under(SHARED):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_str = str(node.module)
                    for pattern in domain_patterns:
                        if pattern in module_str:
                            assert "modules." not in module_str, (
                                f"{_relative_posix(py_file)} imports module domain: {module_str}"
                            )

    def test_src_workers_no_concrete_implementation(self):
        if SRC_WORKERS.is_dir():
            for py_file in _src_files_under(SRC_WORKERS):
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
                            rel = _relative_posix(py_file)
                            allowlist = _load_allowlist("worker_locations")
                            if (rel, target) not in allowlist and (
                                rel.replace("\\", "/"),
                                target,
                            ) not in allowlist:
                                assert False, (
                                    f"{rel} has unlisted module import: {target}"
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

    def test_agent_does_not_import_non_agent_non_legacy_modules(self):
        agent_dir = SRC_MODULES / "agent"
        if not agent_dir.is_dir():
            pytest.skip("agent module does not exist")

        violations = []
        for py_file in _src_files_under(agent_dir):
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
                        if target in AGENT_FORBIDDEN_TARGETS:
                            allowlist = _load_allowlist("module_boundaries")
                            if (rel, target) not in allowlist and (
                                rel.replace("\\", "/"),
                                target,
                            ) not in allowlist:
                                violations.append(
                                    f"{rel} imports forbidden module: {target}"
                                )

        violations.sort()
        assert not violations, (
            "agent imports non-agent, non-legacy modules:\n"
            + "\n".join(violations)
        )

    def test_allowlist_entries_have_removal_spec(self):
        if not ALLOWLIST_FILE.exists():
            return

        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        entries = data.get("entries") or []

        missing = []
        for entry in entries:
            if not entry.get("removal_spec"):
                missing.append(f"{entry.get('file')} -> {entry.get('target_module')}")
            elif not entry.get("scope"):
                missing.append(f"{entry.get('file')} -> {entry.get('target_module')}")

        assert not missing, (
            "Allowlist entries missing removal_spec or scope:\n"
            + "\n".join(missing)
        )

    def test_allowlist_references_valid_files(self):
        if not ALLOWLIST_FILE.exists():
            return

        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        entries = data.get("entries") or []
        for entry in entries:
            file_path = _repository_path(entry["file"])
            assert file_path.exists(), (
                f"Allowlist references non-existent file: {entry['file']}"
            )


class TestAddArchitectureTestsForModuleBoundariesRejectsForbidden:
    """Regression: forbidden patterns are detected."""

    def test_detects_forbidden_cross_module_import(self):
        code = "from modules.core.infra.database.repositories import ProjectRepository\n"
        tree = ast.parse(code)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = str(node.module).split(".")
                if len(parts) >= 2 and parts[0] == "modules":
                    target = parts[1]
                    if target in KNOWN_MODULES and target != "agent":
                        violations.append(target)
        assert violations == ["core"]

    def test_detects_shared_containing_module_domain(self):
        code = "from modules.agent.domain.entities import Agent\n"
        tree = ast.parse(code)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "domain.entities" in str(node.module) and "modules" in str(
                    node.module
                ):
                    found = True
        assert found
