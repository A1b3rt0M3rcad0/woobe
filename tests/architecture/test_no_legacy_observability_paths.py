from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "observability"


class TestNoLegacyObservabilityPaths:
    def test_no_legacy_service_dir(self):
        service_dir = OBSERVABILITY_DIR / "service"
        assert not service_dir.is_dir(), "service/ must be removed"

    def test_no_legacy_infra_models(self):
        path = OBSERVABILITY_DIR / "infra" / "models.py"
        assert not path.is_file(), "infra/models.py shim must be removed"

    def test_no_legacy_infra_repositories(self):
        path = OBSERVABILITY_DIR / "infra" / "repositories.py"
        assert not path.is_file(), "infra/repositories.py shim must be removed"

    def test_no_legacy_infra_mappers(self):
        path = OBSERVABILITY_DIR / "infra" / "mappers.py"
        assert not path.is_file(), "infra/mappers.py shim must be removed"

    def test_canonical_database_models_exist(self):
        path = OBSERVABILITY_DIR / "infra" / "database" / "models.py"
        assert path.is_file(), "infra/database/models.py must exist"

    def test_canonical_database_repositories_exist(self):
        path = OBSERVABILITY_DIR / "infra" / "database" / "repositories.py"
        assert path.is_file(), "infra/database/repositories.py must exist"

    def test_canonical_database_mappers_exist(self):
        path = OBSERVABILITY_DIR / "infra" / "database" / "mappers.py"
        assert path.is_file(), "infra/database/mappers.py must exist"

    def test_canonical_database_unit_of_work_exist(self):
        path = OBSERVABILITY_DIR / "infra" / "database" / "unit_of_work.py"
        assert path.is_file(), "infra/database/unit_of_work.py must exist"
