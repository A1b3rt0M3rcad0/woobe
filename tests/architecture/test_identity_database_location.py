from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_DIR = PROJECT_ROOT / "src" / "modules" / "identity"


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

    def test_old_models_path_is_shim(self):
        path = IDENTITY_DIR / "infra" / "models.py"
        assert path.is_file(), f"Old path removed without shim: {path}"
        content = path.read_text(encoding="utf-8")
        assert "infra.database.models" in content, "Old models.py missing re-export"

    def test_old_repositories_path_is_shim(self):
        path = IDENTITY_DIR / "infra" / "repositories.py"
        assert path.is_file(), f"Old path removed without shim: {path}"
        content = path.read_text(encoding="utf-8")
        assert "infra.database.repositories" in content, "Old repositories.py missing re-export"

    def test_old_mappers_path_is_shim(self):
        path = IDENTITY_DIR / "infra" / "mappers.py"
        assert path.is_file(), f"Old path removed without shim: {path}"
        content = path.read_text(encoding="utf-8")
        assert "infra.database.mappers" in content, "Old mappers.py missing re-export"

    def test_database_init_exports_models(self):
        path = IDENTITY_DIR / "infra" / "database" / "__init__.py"
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "UserModel" in content
        assert "OrganizationModel" in content
        assert "OrganizationMemberModel" in content
        assert "OrganizationInviteModel" in content
        assert "UserSessionModel" in content

    def test_database_init_exports_repositories(self):
        path = IDENTITY_DIR / "infra" / "database" / "__init__.py"
        content = path.read_text(encoding="utf-8")
        assert "SQLAlchemyUserRepository" in content
        assert "SQLAlchemyOrganizationRepository" in content
        assert "SQLAlchemyOutboxEventWriter" in content
