"""Architecture tests for agent dependency-injection bindings."""
import pathlib

import yaml


ALLOWLIST_PATH = pathlib.Path("tests/architecture/legacy_import_allowlist.yaml")
AGENT_COMPOSERS_DIR = pathlib.Path("src/modules/agent/application/composers")
AGENT_USE_CASES_DIR = pathlib.Path("src/modules/agent/application/use_cases")

FORBIDDEN_MODULES = (
    "modules.metering",
    "modules.observability",
    "editions.cloud.billing",
    "modules.identity",
    "modules.tools",
    "modules.core",
)

STREAM_COMPOSERS = {"ask_agent_stream_composer.py"}
READ_ONLY_COMPOSERS = {"get_ask_job_composer.py"}


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
        if entry.get("file", "") == relative_path:
            return True
    return False


class TestDependencyInjectionBindingsSuccess:
    def test_agent_composers_directory_exists(self):
        assert AGENT_COMPOSERS_DIR.is_dir()

    def test_agent_composers_use_agent_repositories(self):
        dirty_composers = []
        for composer_path in AGENT_COMPOSERS_DIR.glob("*.py"):
            if composer_path.name == "__init__.py" or composer_path.name in STREAM_COMPOSERS:
                continue
            violations = _find_forbidden_imports_in_file(composer_path)
            if violations and not _is_violation_allowlisted(composer_path):
                dirty_composers.append((composer_path.name, violations))
        assert not dirty_composers, (
            f"Composers with unallowlisted cross-module imports: {dirty_composers}"
        )

    def test_agent_composers_use_shared_uow_or_agent_uow(self):
        for composer_path in AGENT_COMPOSERS_DIR.glob("*.py"):
            if composer_path.name == "__init__.py" or composer_path.name in STREAM_COMPOSERS or composer_path.name in READ_ONLY_COMPOSERS:
                continue
            content = composer_path.read_text(encoding="utf-8")
            assert (
                "PostgresUnitOfWork" in content
                or "AgentUnitOfWork" in content
                or "TransactionalHandler" in content
            ), f"Composer {composer_path.name} should use a Unit of Work or TransactionalHandler"

    def test_no_agent_composer_instantiates_non_agent_repo_without_allowlist(self):
        for composer_path in AGENT_COMPOSERS_DIR.glob("*.py"):
            if composer_path.name == "__init__.py" or composer_path.name in STREAM_COMPOSERS:
                continue
            content = composer_path.read_text(encoding="utf-8")
            for mod in FORBIDDEN_MODULES:
                if mod in content and not _is_violation_allowlisted(composer_path):
                    assert False, f"{composer_path.name} imports from {mod} without allowlist"


class TestDependencyInjectionBindingsRejectsForbidden:
    def test_detects_composer_importing_non_agent_repository(self):
        forbidden_code = "from editions.cloud.billing.infra.database.repositories import FakeRepo"
        assert any(mod in forbidden_code for mod in FORBIDDEN_MODULES)

    def test_detects_agent_use_case_importing_non_agent_repository(self):
        if not AGENT_USE_CASES_DIR.is_dir():
            return
        for uc_path in AGENT_USE_CASES_DIR.glob("*.py"):
            if uc_path.name == "__init__.py":
                continue
            violations = _find_forbidden_imports_in_file(uc_path)
            if violations:
                assert _is_violation_allowlisted(uc_path), (
                    f"Use case {uc_path.name} has cross-module imports without allowlist: {violations}"
                )


class TestDependencyInjectionBindingsKeepsLegacyCompatibility:
    def test_legacy_cross_module_imports_resolved(self):
        composer = pathlib.Path("src/modules/agent/application/composers/ask_agent_composer.py")
        assert composer.is_file()
        violations = _find_forbidden_imports_in_file(composer)
        assert not violations, f"ask_agent_composer.py should have no cross-module imports: {violations}"

    def test_allowlist_has_no_unknown_files(self):
        root = pathlib.Path(".")
        for entry in _load_allowlist():
            entry_file = entry.get("file", "")
            if entry_file:
                assert (root / entry_file).is_file(), (
                    f"Allowlist references non-existent file: {entry_file}"
                )
