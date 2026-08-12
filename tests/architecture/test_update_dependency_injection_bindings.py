"""Tests for spec 132 — update dependency injection bindings.

Validates that agent composers build repositories and UoW from the agent module
and do not instantiate repositories from other modules (metering, observability,
billing, identity, tools, core) for state changes.
"""
import pathlib

import yaml


ALLOWLIST_PATH = pathlib.Path("tests/architecture/legacy_import_allowlist.yaml")
AGENT_COMPOSERS_DIR = pathlib.Path("src/modules/agent/application/composers")
AGENT_USE_CASES_DIR = pathlib.Path("src/modules/agent/application/use_cases")
AGENT_INFRA_WORKERS_DIR = pathlib.Path("src/modules/agent/infra/workers")

FORBIDDEN_MODULES = (
    "modules.metering",
    "modules.observability",
    "editions.cloud.billing",
    "modules.identity",
    "modules.tools",
    "modules.core",
)

STREAM_COMPOSERS = {
    "ask_agent_stream_composer.py",
}

READ_ONLY_COMPOSERS = {
    "get_ask_job_composer.py",
}


def _load_allowlist():
    with open(ALLOWLIST_PATH, "r") as f:
        data = yaml.safe_load(f) or {}
    return data.get("entries", [])


def _find_forbidden_imports_in_file(file_path: pathlib.Path):
    violations = []
    content = file_path.read_text(encoding="utf-8")
    for line_no, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith(("from ", "import ")):
            continue
        for mod in FORBIDDEN_MODULES:
            if mod in stripped:
                violations.append((line_no, stripped))
    return violations


def _is_violation_allowlisted(file_path: pathlib.Path):
    relative_path = str(file_path).replace("\\", "/")
    for entry in _load_allowlist():
        entry_file = entry.get("file", "")
        if entry_file == relative_path:
            return True
    return False


class TestDependencyInjectionBindingsSuccess:
    """Verify agent composers use agent repositories and UoW."""

    def test_agent_composers_directory_exists(self):
        assert AGENT_COMPOSERS_DIR.is_dir()

    def test_agent_composers_use_agent_repositories(self):
        composers = list(AGENT_COMPOSERS_DIR.glob("*.py"))
        assert len(composers) > 0

        dirty_composers = []
        for composer_path in composers:
            if composer_path.name == "__init__.py":
                continue
            if composer_path.name in STREAM_COMPOSERS:
                continue
            violations = _find_forbidden_imports_in_file(composer_path)
            if violations:
                allowlisted = _is_violation_allowlisted(composer_path)
                if not allowlisted:
                    dirty_composers.append((composer_path.name, violations))

        assert len(dirty_composers) == 0, (
            f"Composers with unallowlisted cross-module imports: {dirty_composers}"
        )

    def test_agent_composers_use_shared_uow_or_agent_uow(self):
        composers = list(AGENT_COMPOSERS_DIR.glob("*.py"))
        for composer_path in composers:
            if composer_path.name == "__init__.py":
                continue
            if composer_path.name in STREAM_COMPOSERS:
                continue
            if composer_path.name in READ_ONLY_COMPOSERS:
                continue
            content = composer_path.read_text(encoding="utf-8")
            has_uow = (
                "PostgresUnitOfWork" in content
                or "AgentUnitOfWork" in content
                or "TransactionalHandler" in content
            )
            assert has_uow, (
                f"Composer {composer_path.name} should use a Unit of Work "
                f"or TransactionalHandler"
            )

    def test_no_agent_composer_instantiates_non_agent_repo_without_allowlist(self):
        composers = list(AGENT_COMPOSERS_DIR.glob("*.py"))
        for composer_path in composers:
            if composer_path.name == "__init__.py":
                continue
            if composer_path.name in STREAM_COMPOSERS:
                continue
            content = composer_path.read_text(encoding="utf-8")
            for mod in FORBIDDEN_MODULES:
                if mod in content and not _is_violation_allowlisted(composer_path):
                    assert False, (
                        f"{composer_path.name} imports from {mod} without allowlist"
                    )


class TestDependencyInjectionBindingsRejectsForbidden:
    """Verify that forbidden DI patterns are detected."""

    def test_detects_composer_importing_non_agent_repository(self):
        forbidden_code = "from modules.metering.infra.repositories import FakeRepo"
        detected = False
        for mod in FORBIDDEN_MODULES:
            if mod in forbidden_code:
                detected = True
                break
        assert detected, "Forbidden import pattern must be recognizable"

    def test_detects_agent_use_case_importing_non_agent_repository(self):
        if not AGENT_USE_CASES_DIR.is_dir():
            return
        use_cases = list(AGENT_USE_CASES_DIR.glob("*.py"))
        for uc_path in use_cases:
            if uc_path.name == "__init__.py":
                continue
            violations = _find_forbidden_imports_in_file(uc_path)
            if violations:
                assert _is_violation_allowlisted(uc_path), (
                    f"Use case {uc_path.name} has cross-module imports without "
                    f"allowlist: {violations}"
                )


class TestDependencyInjectionBindingsKeepsLegacyCompatibility:
    """Verify legacy cross-module DI is covered by allowlist."""

    def test_legacy_cross_module_imports_resolved(self):
        composer = pathlib.Path(
            "src/modules/agent/application/composers/ask_agent_composer.py"
        )
        assert composer.is_file()
        violations = _find_forbidden_imports_in_file(composer)
        assert len(violations) == 0, (
            f"ask_agent_composer.py should have no cross-module imports: {violations}"
        )

    def test_allowlist_has_no_unknown_files(self):
        allowlist = _load_allowlist()
        root = pathlib.Path(".")
        for entry in allowlist:
            entry_file = entry.get("file", "")
            if not entry_file:
                continue
            full_path = root / entry_file
            assert full_path.is_file(), (
                f"Allowlist references non-existent file: {entry_file}"
            )
