from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
IDENTITY_DIR = PROJECT_ROOT / "src" / "modules" / "identity"
UOW_FILE = IDENTITY_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = IDENTITY_DIR / "application" / "composers"


class TestIdentityUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file(), f"IdentityUnitOfWork file missing: {UOW_FILE}"

    def test_uow_class_name(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class IdentityUnitOfWork" in content

    def test_uow_extends_unit_of_work(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "UnitOfWork" in content

    def test_uow_has_users_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def users" in content
        assert "SQLAlchemyUserRepository" in content

    def test_uow_has_workspaces_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def workspaces" in content
        assert "SQLAlchemyWorkspaceRepository" in content

    def test_uow_has_members_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def members" in content
        assert "SQLAlchemyWorkspaceMemberRepository" in content

    def test_uow_has_invites_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def invites" in content
        assert "SQLAlchemyWorkspaceInviteRepository" in content

    def test_uow_has_user_sessions_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def user_sessions" in content
        assert "SQLAlchemyUserSessionRepository" in content

    def test_uow_has_outbox_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def outbox" in content
        assert "SQLAlchemyOutboxEventWriter" in content

    def test_uow_has_commit_and_rollback(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "async def commit" in content
        assert "async def rollback" in content

    def test_uow_has_aenter_aexit(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "__aenter__" in content
        assert "__aexit__" in content

    def test_uow_reinitializes_none_on_exit(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "self._users = None" in content
        assert "self._workspaces = None" in content
        assert "self._outbox = None" in content

    def test_no_composer_imports_postgres_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "PostgresUnitOfWork" not in source, (
                f"{py_file.name} still imports PostgresUnitOfWork"
            )

    def test_all_composers_import_identity_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "IdentityUnitOfWork" in source, (
                f"{py_file.name} does not import IdentityUnitOfWork"
            )

    def test_all_composers_use_uow_dot_property_pattern(self):
        skip = {"get_current_user_composer.py"}
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            if py_file.name in skip:
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "uow." in source, (
                f"{py_file.name} does not use uow.property pattern"
            )
