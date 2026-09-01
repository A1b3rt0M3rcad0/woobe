from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core"


class TestCoreDatabaseLocation:
    def test_database_models_in_canonical_location(self):
        path = CORE_DIR / "infra" / "database" / "models.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_repositories_in_canonical_location(self):
        path = CORE_DIR / "infra" / "database" / "repositories.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_mappers_in_canonical_location(self):
        path = CORE_DIR / "infra" / "database" / "mappers.py"
        assert path.is_file(), f"Missing: {path}"

    def test_old_models_path_removed(self):
        path = CORE_DIR / "infra" / "models.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_old_repositories_path_removed(self):
        path = CORE_DIR / "infra" / "repositories.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_old_mappers_path_removed(self):
        path = CORE_DIR / "infra" / "mappers.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_database_init_exports_models(self):
        path = CORE_DIR / "infra" / "database" / "__init__.py"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "ProjectModel" in content
        assert "ApiKeyModel" in content
        assert "OutboxEventModel" in content
        assert "InboxEventModel" in content

    def test_database_init_exports_repositories(self):
        path = CORE_DIR / "infra" / "database" / "__init__.py"
        content = path.read_text(encoding="utf-8")
        assert "SQLAlchemyProjectRepository" in content
        assert "SQLAlchemyApiKeyRepository" in content
        assert "SQLAlchemyOutboxEventWriter" in content
