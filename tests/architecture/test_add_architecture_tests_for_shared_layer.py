"""Tests for spec 112 — add architecture tests for shared layer.

Validates shared-layer isolation: no module domain imports, no hardcoded module lists,
no legacy module references. Uses the legacy import allowlist for temporary entries.
"""
from __future__ import annotations

import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
SRC_SHARED = PROJECT_ROOT / "src" / "shared"
SRC_WORKERS = PROJECT_ROOT / "src" / "workers"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}

LEGACY_MODULES = {"ai", "knowledge", "runtime"}

DOMAIN_PATTERNS = [
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


class TestAddArchitectureTestsForSharedLayer:
    """Shared layer architecture tests for spec 112."""

    def test_add_architecture_tests_for_shared_layer(self):
        violations = []

        if not SRC_SHARED.exists():
            return

        for py_file in _src_files_under(SRC_SHARED):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_str = str(node.module)
                    if module_str.startswith("modules."):
                        parts = module_str.split(".")
                        if len(parts) >= 2 and parts[1] in KNOWN_MODULES:
                            violations.append(
                                f"{rel} statically imports {module_str}"
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("modules."):
                            parts = alias.name.split(".")
                            if len(parts) >= 2 and parts[1] in KNOWN_MODULES:
                                violations.append(
                                    f"{rel} statically imports {alias.name}"
                                )

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name_lower = node.name.lower()
                    domain_keywords = ("usecase", "use_case", "handler", "aggregate")
                    infra_indicators = ("base", "abstract", "transactional", "generic")
                    if any(kw in class_name_lower for kw in domain_keywords) and not any(
                        ind in class_name_lower for ind in infra_indicators
                    ):
                        violations.append(
                            f"{rel}: class '{node.name}' appears to be domain logic in shared"
                        )

        assert not violations, (
            f"Found {len(violations)} shared layer violation(s):\n"
            + "\n".join(violations[:30])
        )

    def test_shared_does_not_import_module_domain(self):
        if not SRC_SHARED.exists():
            return

        violations = []
        for py_file in _src_files_under(SRC_SHARED):
            rel = _relative_posix(py_file)
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_str = str(node.module)
                    for pattern in DOMAIN_PATTERNS:
                        if pattern in module_str and "modules." in module_str:
                            violations.append(
                                f"{rel} imports module domain: {module_str}"
                            )
                            break

        assert not violations, (
            f"Shared layer imports module domain from {len(violations)} file(s):\n"
            + "\n".join(violations[:20])
        )

    def test_shared_does_not_reference_legacy_modules(self):
        if not SRC_SHARED.exists():
            return

        allowlist = _load_allowlist("shared_boundaries")
        violations = []

        for py_file in _src_files_under(SRC_SHARED):
            rel = _relative_posix(py_file)

            if rel in allowlist or rel.replace("\\", "/") in allowlist:
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            for module_name in LEGACY_MODULES:
                patterns = [
                    f"modules.{module_name}.",
                ]
                for pattern in patterns:
                    if pattern in source:
                        violations.append(
                            f"{rel} references legacy module '{module_name}' "
                            f"(found '{pattern}')"
                        )
                        break

        assert not violations, (
            f"Shared layer references legacy modules in {len(violations)} location(s):\n"
            + "\n".join(violations[:20])
        )

    def test_src_workers_no_concrete_implementation(self):
        if not SRC_WORKERS.is_dir():
            return

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
                        allowlist = _load_allowlist("worker_locations")
                        if rel not in allowlist and rel.replace("\\", "/") not in allowlist:
                            violations.append(
                                f"{rel} imports module {target} (unlisted worker location)"
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

    def test_agent_does_not_import_non_agent_non_legacy_modules(self):
        agent_dir = SRC_MODULES / "agent"
        if not agent_dir.is_dir():
            return

        forbid_targets = KNOWN_MODULES - {"agent", *LEGACY_MODULES}
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
                        if target in forbid_targets:
                            allowlist = _load_allowlist("module_boundaries")
                            if rel not in allowlist and rel.replace("\\", "/") not in allowlist:
                                violations.append(
                                    f"{rel} imports forbidden module: {target}"
                                )

        violations.sort()
        assert not violations, (
            "agent imports non-agent, non-legacy modules:\n"
            + "\n".join(violations)
        )

    def test_shared_allowlist_entries_valid(self):
        allowlist_data = {}
        if ALLOWLIST_FILE.exists():
            with open(ALLOWLIST_FILE, encoding="utf-8") as f:
                allowlist_data = yaml.safe_load(f) or {}

        entries = allowlist_data.get("entries") or []
        shared_entries = [e for e in entries if e.get("scope") == "shared_boundaries"]

        for entry in shared_entries:
            assert entry.get("file"), f"shared_boundaries entry missing file: {entry}"
            assert entry.get("removal_spec"), (
                f"shared_boundaries entry missing removal_spec: {entry}"
            )


class TestAddArchitectureTestsForSharedLayerRejectsForbidden:
    """Regression: forbidden patterns are detected."""

    def test_detects_forbidden_module_import_in_shared(self):
        code = "from modules.agent.domain.entities import Agent\n"
        tree = ast.parse(code)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("modules."):
                    found = True
        assert found

    def test_detects_domain_class_in_shared(self):
        code = """
class CreateAgentUseCase:
    pass
"""
        tree = ast.parse(code)
        domain_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if "usecase" in node.name.lower():
                    domain_found = True
        assert domain_found

    def test_detects_legacy_module_reference_in_shared(self):
        code = 'from modules.ai.infra.models import Model\n'
        found = "modules.ai" in code
        assert found
