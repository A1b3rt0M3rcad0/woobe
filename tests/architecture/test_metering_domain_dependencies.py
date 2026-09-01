import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
METERING_DOMAIN_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "metering" / "domain"

FORBIDDEN_IMPORTS = {"sqlalchemy", "fastapi"}


def _get_import_strings_from_file(filepath: Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


class TestMeteringDomainDependencies:
    def test_domain_does_not_import_forbidden_frameworks(self):
        py_files = list(METERING_DOMAIN_DIR.rglob("*.py"))
        assert len(py_files) > 0, "Metering domain must have Python files"

        violations = []
        for filepath in sorted(py_files):
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                for forbidden in FORBIDDEN_IMPORTS:
                    if imp.startswith(forbidden):
                        violations.append(f"{filepath.name}: imports '{imp}'")

        assert not violations, (
            f"Metering domain must not import forbidden frameworks: {violations}"
        )

    def test_domain_entities_exist(self):
        entities_file = METERING_DOMAIN_DIR / "entities.py"
        assert entities_file.is_file(), "metering/domain/entities.py must exist"
        source = entities_file.read_text(encoding="utf-8")
        assert "class UsageEvent" in source, "entities.py must define UsageEvent"
        assert "class UsageDailyProject" in source, "entities.py must define UsageDailyProject"
        assert "class UsageDailyAgent" in source, "entities.py must define UsageDailyAgent"

    def test_domain_repositories_are_abstract(self):
        repos_file = METERING_DOMAIN_DIR / "repositories.py"
        assert repos_file.is_file(), "metering/domain/repositories.py must exist"
        source = repos_file.read_text(encoding="utf-8")
        for repo_name in ("UsageEventRepository", "UsageDailyProjectRepository",
                          "UsageDailyAgentRepository"):
            assert f"class {repo_name}" in source, f"repositories.py must define {repo_name}"

        assert "ABC" in source, "repositories must use ABC"
