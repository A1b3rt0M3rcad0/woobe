import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
METERING_INFRA_DIR = PROJECT_ROOT / "src" / "modules" / "metering" / "infra"
METERING_DB_DIR = METERING_INFRA_DIR / "database"


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


class TestMeteringDatabaseLocation:
    def test_database_directory_exists(self):
        assert METERING_DB_DIR.is_dir(), (
            "metering/infra/database/ must exist"
        )

    def test_database_models_exist(self):
        assert (METERING_DB_DIR / "models.py").is_file(), (
            "metering/infra/database/models.py must exist"
        )

    def test_database_repositories_exist(self):
        assert (METERING_DB_DIR / "repositories.py").is_file(), (
            "metering/infra/database/repositories.py must exist"
        )

    def test_database_mappers_exist(self):
        assert (METERING_DB_DIR / "mappers.py").is_file(), (
            "metering/infra/database/mappers.py must exist"
        )

    def test_infra_models_is_shim(self):
        path = METERING_INFRA_DIR / "models.py"
        assert path.is_file(), "metering/infra/models.py must exist as shim"
        imports = _get_import_strings_from_file(path)
        assert any("infra.database.models" in i for i in imports), (
            "metering/infra/models.py must import from infra/database/models"
        )

    def test_infra_repositories_is_shim(self):
        path = METERING_INFRA_DIR / "repositories.py"
        assert path.is_file(), "metering/infra/repositories.py must exist as shim"
        imports = _get_import_strings_from_file(path)
        assert any("infra.database.repositories" in i for i in imports), (
            "metering/infra/repositories.py must import from infra/database/repositories"
        )

    def test_infra_mappers_is_shim(self):
        path = METERING_INFRA_DIR / "mappers.py"
        assert path.is_file(), "metering/infra/mappers.py must exist as shim"
        imports = _get_import_strings_from_file(path)
        assert any("infra.database.mappers" in i for i in imports), (
            "metering/infra/mappers.py must import from infra/database/mappers"
        )

    def test_repositories_import_from_canonical_models(self):
        path = METERING_DB_DIR / "repositories.py"
        imports = _get_import_strings_from_file(path)
        assert any("infra.database.models" in i for i in imports), (
            "infra/database/repositories.py must import from infra/database/models"
        )

    def test_mappers_import_from_canonical_models(self):
        path = METERING_DB_DIR / "mappers.py"
        imports = _get_import_strings_from_file(path)
        assert any("infra.database.models" in i for i in imports), (
            "infra/database/mappers.py must import from infra/database/models"
        )

    def test_no_repository_concrete_outside_database(self):
        infra_py_files = [
            p for p in METERING_INFRA_DIR.rglob("*.py")
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
