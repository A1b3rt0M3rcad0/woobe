import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_INFRA_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "observability" / "infra"
OBSERVABILITY_DB_DIR = OBSERVABILITY_INFRA_DIR / "database"


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


class TestObservabilityDatabaseLocation:
    def test_database_directory_exists(self):
        assert OBSERVABILITY_DB_DIR.is_dir(), (
            "observability/infra/database/ must exist"
        )

    def test_database_models_exist(self):
        assert (OBSERVABILITY_DB_DIR / "models.py").is_file(), (
            "observability/infra/database/models.py must exist"
        )

    def test_database_repositories_exist(self):
        assert (OBSERVABILITY_DB_DIR / "repositories.py").is_file(), (
            "observability/infra/database/repositories.py must exist"
        )

    def test_database_mappers_exist(self):
        assert (OBSERVABILITY_DB_DIR / "mappers.py").is_file(), (
            "observability/infra/database/mappers.py must exist"
        )

    def test_repositories_import_from_canonical_models(self):
        path = OBSERVABILITY_DB_DIR / "repositories.py"
        imports = _get_import_strings_from_file(path)
        assert any("infra.database.models" in i for i in imports), (
            "infra/database/repositories.py must import from infra/database/models"
        )

    def test_mappers_import_from_canonical_models(self):
        path = OBSERVABILITY_DB_DIR / "mappers.py"
        imports = _get_import_strings_from_file(path)
        assert any("infra.database.models" in i for i in imports), (
            "infra/database/mappers.py must import from infra/database/models"
        )

    def test_no_infra_flat_models_shim(self):
        path = OBSERVABILITY_INFRA_DIR / "models.py"
        assert not path.is_file(), "observability/infra/models.py shim must be removed"

    def test_no_infra_flat_repositories_shim(self):
        path = OBSERVABILITY_INFRA_DIR / "repositories.py"
        assert not path.is_file(), "observability/infra/repositories.py shim must be removed"

    def test_no_infra_flat_mappers_shim(self):
        path = OBSERVABILITY_INFRA_DIR / "mappers.py"
        assert not path.is_file(), "observability/infra/mappers.py shim must be removed"

    def test_no_repository_concrete_outside_database(self):
        infra_py_files = [
            p for p in OBSERVABILITY_INFRA_DIR.rglob("*.py")
            if p.name != "__init__.py" and p.parent.name != "database"
            and p.parent.parent.name != "database"
            and "messaging" not in str(p)
            and "workers" not in str(p)
        ]
        violations = []
        for filepath in sorted(infra_py_files):
            source = filepath.read_text(encoding="utf-8")
            if "class SQLAlchemy" in source or "class.*Repository" in source:
                violations.append(filepath.name)
        assert not violations, (
            f"Repository classes must only live in infra/database/, found in: {violations}"
        )
