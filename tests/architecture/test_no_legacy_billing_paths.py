from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BILLING_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "billing"


class TestNoLegacyBillingPaths:
    def test_service_directory_removed(self):
        path = BILLING_DIR / "service"
        assert not path.exists(), f"Legacy service/ still exists: {path}"

    def test_infra_models_shim_removed(self):
        path = BILLING_DIR / "infra" / "models.py"
        assert not path.exists(), f"Legacy infra/models.py still exists: {path}"

    def test_infra_repositories_shim_removed(self):
        path = BILLING_DIR / "infra" / "repositories.py"
        assert not path.exists(), f"Legacy infra/repositories.py still exists: {path}"

    def test_infra_mappers_shim_removed(self):
        path = BILLING_DIR / "infra" / "mappers.py"
        assert not path.exists(), f"Legacy infra/mappers.py still exists: {path}"

    def test_canonical_models_exist(self):
        path = BILLING_DIR / "infra" / "database" / "models.py"
        assert path.is_file()

    def test_canonical_repositories_exist(self):
        path = BILLING_DIR / "infra" / "database" / "repositories.py"
        assert path.is_file()

    def test_canonical_mappers_exist(self):
        path = BILLING_DIR / "infra" / "database" / "mappers.py"
        assert path.is_file()

    def test_canonical_unit_of_work_exist(self):
        path = BILLING_DIR / "infra" / "database" / "unit_of_work.py"
        assert path.is_file()
