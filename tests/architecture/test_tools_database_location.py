from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = PROJECT_ROOT / "src" / "modules" / "tools"


class TestToolsDatabaseLocation:
    def test_database_models_in_canonical_location(self):
        path = TOOLS_DIR / "infra" / "database" / "models.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_repositories_in_canonical_location(self):
        path = TOOLS_DIR / "infra" / "database" / "repositories.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_mappers_in_canonical_location(self):
        path = TOOLS_DIR / "infra" / "database" / "mappers.py"
        assert path.is_file(), f"Missing: {path}"

    def test_old_models_shim_exists(self):
        path = TOOLS_DIR / "infra" / "models.py"
        assert path.is_file(), f"Shim must exist: {path}"

    def test_old_repositories_shim_exists(self):
        path = TOOLS_DIR / "infra" / "repositories.py"
        assert path.is_file(), f"Shim must exist: {path}"

    def test_old_mappers_shim_exists(self):
        path = TOOLS_DIR / "infra" / "mappers.py"
        assert path.is_file(), f"Shim must exist: {path}"

    def test_database_init_exports_models(self):
        path = TOOLS_DIR / "infra" / "database" / "__init__.py"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "ToolModel" in content
        assert "SecretModel" in content
        assert "OutboxEventModel" in content
        assert "InboxEventModel" in content

    def test_database_init_exports_repositories(self):
        path = TOOLS_DIR / "infra" / "database" / "__init__.py"
        content = path.read_text(encoding="utf-8")
        assert "SQLAlchemyToolRepository" in content
        assert "SQLAlchemySecretRepository" in content
        assert "SQLAlchemyOutboxEventWriter" in content
