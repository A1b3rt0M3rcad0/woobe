from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "src" / "modules" / "tools"


class TestNoLegacyToolsPaths:
    def test_no_service_directory(self):
        path = TOOLS_DIR / "service"
        assert not path.is_dir(), "tools/service/ must be removed"

    def test_no_infra_flat_models(self):
        path = TOOLS_DIR / "infra" / "models.py"
        assert not path.is_file(), "tools/infra/models.py must be removed"

    def test_no_infra_flat_repositories(self):
        path = TOOLS_DIR / "infra" / "repositories.py"
        assert not path.is_file(), "tools/infra/repositories.py must be removed"

    def test_no_infra_flat_mappers(self):
        path = TOOLS_DIR / "infra" / "mappers.py"
        assert not path.is_file(), "tools/infra/mappers.py must be removed"

    def test_canonical_models_in_database(self):
        path = TOOLS_DIR / "infra" / "database" / "models.py"
        assert path.is_file(), "tools/infra/database/models.py must exist"

    def test_canonical_repositories_in_database(self):
        path = TOOLS_DIR / "infra" / "database" / "repositories.py"
        assert path.is_file(), "tools/infra/database/repositories.py must exist"

    def test_canonical_mappers_in_database(self):
        path = TOOLS_DIR / "infra" / "database" / "mappers.py"
        assert path.is_file(), "tools/infra/database/mappers.py must exist"

    def test_canonical_uow_in_database(self):
        path = TOOLS_DIR / "infra" / "database" / "unit_of_work.py"
        assert path.is_file(), "tools/infra/database/unit_of_work.py must exist"
