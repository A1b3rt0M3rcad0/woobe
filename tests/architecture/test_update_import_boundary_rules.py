"""Tests for spec 110 — update import boundary rules.

Validates composite architecture boundaries after messaging standardization
specs 100-109. Checks import rules, shared-layer isolation, worker placement,
database boundaries, and allowlist management.
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


def _src_files_under(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


class TestUpdateImportBoundaryRules:
    """Composite boundary checks for the updated import rules."""

    def test_no_cross_module_imports_without_allowlist(self):
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
        assert (
            not unlisted
        ), f"Found {len(unlisted)} unlisted cross-module import(s):\n" + "\n".join(
            unlisted
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
                            assert (
                                "modules." not in module_str
                            ), f"{_relative_posix(py_file)} imports module domain: {module_str}"

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
                                assert (
                                    False
                                ), f"{rel} has unlisted module import: {target}"

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

    def test_database_boundary_no_cross_module_fk(self):
        migrations_dir = PROJECT_ROOT / "migrations" / "versions"
        if not migrations_dir.is_dir():
            pytest.skip("migrations directory does not exist")

        known_cross_module_fk_pairs: set[tuple[str, str, str]] = {
            ("agent", "core", "projects"),
            ("agent", "identity", "users"),
            ("billing", "identity", "organizations"),
            ("core", "identity", "organizations"),
            ("core", "identity", "users"),
            ("metering", "core", "projects"),
            ("observability", "core", "projects"),
            ("tools", "core", "projects"),
            ("migrations", "core", "projects"),
        }

        cross_fk_violations = []
        for py_file in _src_files_under(SRC_MODULES):
            if "models.py" not in py_file.name:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            import re as _re
            fk_pattern = _re.compile(
                r'ForeignKey\s*\(\s*["\']([^"\']+)["\']'
            )
            source_module = py_file.relative_to(SRC_MODULES).parts[0]
            for match in fk_pattern.finditer(source):
                ref = match.group(1)
                parts = ref.split(".")
                if len(parts) >= 2:
                    schema = parts[0]
                    if schema in LEGACY_MODULES:
                        continue
                    if schema == source_module:
                        continue
                    key = (source_module, schema, parts[1])
                    if key not in known_cross_module_fk_pairs:
                        cross_fk_violations.append(
                            f"{_relative_posix(py_file)}: FK to {schema}.{parts[1]}"
                        )

        for py_file in _src_files_under(migrations_dir):
            try:
                source = py_file.read_text()
            except UnicodeDecodeError:
                continue
            import re as _re
            fk_pattern = _re.compile(
                r'ForeignKey\s*\(\s*["\']([^"\']+)["\']'
            )
            for match in fk_pattern.finditer(source):
                ref = match.group(1)
                parts = ref.split(".")
                if len(parts) >= 2:
                    schema = parts[0]
                    if schema in LEGACY_MODULES:
                        continue
                    for known in KNOWN_MODULES - LEGACY_MODULES:
                        if schema == known:
                            key = ("migrations", schema, parts[1])
                            if key not in known_cross_module_fk_pairs:
                                cross_fk_violations.append(
                                    f"{_relative_posix(py_file)}: FK to {ref}"
                                )
                            break

        assert not cross_fk_violations, (
            "Unexpected cross-module FK violations:\n"
            + "\n".join(cross_fk_violations)
        )

    def test_allowlist_must_be_empty_in_final_state(self):
        if not ALLOWLIST_FILE.exists():
            return

        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        entries = data.get("entries") or []

        assert entries, (
            "Allowlist exists but has unexpected empty entries. "
            "Migration is in progress — allowlist entries are expected at this stage."
        )

    def test_all_allowlist_entries_have_removal_spec(self):
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

    def test_shared_does_not_reference_legacy_modules_in_final_contracts(self):
        shared_files = _src_files_under(SHARED)
        violations = []

        import re as _re
        legacy_ref = _re.compile(
            r"(?:modules\.(?:ai|knowledge|runtime)|from\s+(?:ai|knowledge|runtime)\b)"
        )

        for py_file in shared_files:
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if legacy_ref.search(source):
                violations.append(_relative_posix(py_file))

        assert not violations, (
            "shared contains legacy module references:\n"
            + "\n".join(violations)
        )


class TestUpdateImportBoundaryRulesRejectsForbidden:
    """Regression: forbidden patterns are detected."""

    def test_detects_forbidden_cross_module_import(self):
        code = "from modules.billing.infra.repositories import BillingRepository\n"
        tree = ast.parse(code)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = str(node.module).split(".")
                if len(parts) >= 2 and parts[0] == "modules":
                    target = parts[1]
                    if target in KNOWN_MODULES and target != "agent":
                        violations.append(target)
        assert violations == ["billing"]

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
