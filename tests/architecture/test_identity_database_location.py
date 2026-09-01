from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "identity"


class TestIdentityDatabaseLocation:
    def test_database_models_in_canonical_location(self):
        path = IDENTITY_DIR / "infra" / "database" / "models.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_repositories_in_canonical_location(self):
        path = IDENTITY_DIR / "infra" / "database" / "repositories.py"
        assert path.is_file(), f"Missing: {path}"

    def test_database_mappers_in_canonical_location(self):
        path = IDENTITY_DIR / "infra" / "database" / "mappers.py"
        assert path.is_file(), f"Missing: {path}"

    def test_old_models_path_removed(self):
        path = IDENTITY_DIR / "infra" / "models.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_old_repositories_path_removed(self):
        path = IDENTITY_DIR / "infra" / "repositories.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_old_mappers_path_removed(self):
        path = IDENTITY_DIR / "infra" / "mappers.py"
        assert not path.exists(), f"Old path should be removed: {path}"

    def test_database_init_exports_models(self):
        path = IDENTITY_DIR / "infra" / "database" / "__init__.py"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "UserModel" in content
        assert "WorkspaceModel" in content
        assert "WorkspaceMemberModel" in content
        assert "WorkspaceInviteModel" in content
        assert "UserSessionModel" in content

    def test_database_init_exports_repositories(self):
        path = IDENTITY_DIR / "infra" / "database" / "__init__.py"
        content = path.read_text(encoding="utf-8")
        assert "SQLAlchemyUserRepository" in content
        assert "SQLAlchemyWorkspaceRepository" in content
        assert "SQLAlchemyOutboxEventWriter" in content
