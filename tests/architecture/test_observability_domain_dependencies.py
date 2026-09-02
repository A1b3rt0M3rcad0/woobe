import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_DIR = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "observability"
)
OBSERVABILITY_DOMAIN_DIR = OBSERVABILITY_DIR / "domain"
OBSERVABILITY_INTERFACES_DIR = OBSERVABILITY_DIR / "application" / "interfaces"
FORBIDDEN_IMPORTS = {"sqlalchemy", "fastapi"}


def _get_import_strings_from_file(filepath: Path) -> list[str]:
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


class TestObservabilityDomainDependencies:
    def test_domain_does_not_import_forbidden_frameworks(self):
        py_files = list(OBSERVABILITY_DOMAIN_DIR.rglob("*.py"))
        assert py_files, "Observability domain must have Python files"
        violations = []
        for filepath in sorted(py_files):
            for imported in _get_import_strings_from_file(filepath):
                for forbidden in FORBIDDEN_IMPORTS:
                    if imported.startswith(forbidden):
                        violations.append(f"{filepath.name}: imports '{imported}'")
        assert not violations, (
            f"Observability domain must not import forbidden frameworks: {violations}"
        )

    def test_domain_entities_exist(self):
        entities_file = OBSERVABILITY_DOMAIN_DIR / "entities.py"
        assert entities_file.is_file()
        source = entities_file.read_text(encoding="utf-8")
        assert "class Trace" in source
        assert "class TraceEvent" in source

    def test_repository_ports_belong_to_application(self):
        repos_file = OBSERVABILITY_INTERFACES_DIR / "repositories.py"
        assert repos_file.is_file()
        source = repos_file.read_text(encoding="utf-8")
        assert "class TraceRepository" in source
        assert "class TraceEventRepository" in source
        assert "ABC" in source
        assert "abstractmethod" in source
        assert not (OBSERVABILITY_DOMAIN_DIR / "repositories.py").exists()

    def test_domain_errors_exist(self):
        errors_file = OBSERVABILITY_DOMAIN_DIR / "errors.py"
        assert errors_file.is_file()
        assert "class TraceNotFoundError" in errors_file.read_text(encoding="utf-8")
