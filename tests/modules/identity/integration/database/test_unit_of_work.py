from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
IDENTITY_DIR = PROJECT_ROOT / "src" / "modules" / "identity"
UOW_FILE = IDENTITY_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = IDENTITY_DIR / "composition" / "composers"


class TestIdentityUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file(), f"IdentityUnitOfWork file missing: {UOW_FILE}"

    def test_uow_owns_session_lifecycle(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class IdentityUnitOfWork" in content
        assert "def __init__(self, engine: AsyncEngine)" in content
        assert "async_sessionmaker(" in content
        assert "def session" in content
        assert "async def __aenter__" in content
        assert "async def __aexit__" in content
        assert "async def commit" in content
        assert "async def rollback" in content

    def test_uow_is_not_repository_locator(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        forbidden = (
            "def users",
            "def workspaces",
            "def members",
            "def invites",
            "def user_sessions",
            "def outbox",
            "SQLAlchemyUserRepository",
            "SQLAlchemyWorkspaceRepository",
            "SQLAlchemyWorkspaceMemberRepository",
            "SQLAlchemyWorkspaceInviteRepository",
            "SQLAlchemyUserSessionRepository",
            "SQLAlchemyOutboxEventWriter",
        )
        violations = [marker for marker in forbidden if marker in content]
        assert not violations, f"UoW still exposes repositories: {violations}"

    def test_composers_use_canonical_engine_owned_uow(self):
        py_files = sorted(
            path
            for path in COMPOSERS_DIR.glob("*.py")
            if not path.name.startswith("__")
        )
        assert py_files, "Identity composition must contain composers"
        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "IdentityUnitOfWork" not in source:
                violations.append(f"{py_file.name}: missing IdentityUnitOfWork")
            if "IdentityUnitOfWork(DATABASE_ENGINE)" not in source:
                violations.append(f"{py_file.name}: UoW not built from DATABASE_ENGINE")
            for locator in ("uow.users", "uow.workspaces", "uow.members", "uow.invites", "uow.user_sessions", "uow.outbox"):
                if locator in source:
                    violations.append(f"{py_file.name}: repository locator {locator}")
        assert not violations, "\n".join(violations)
