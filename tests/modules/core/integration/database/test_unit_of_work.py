from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CORE_DIR = PROJECT_ROOT / "src" / "modules" / "core"
UOW_FILE = CORE_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = CORE_DIR / "application" / "composers"


class TestCoreUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file(), f"CoreUnitOfWork file missing: {UOW_FILE}"

    def test_uow_class_name(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class CoreUnitOfWork" in content

    def test_uow_extends_unit_of_work(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "UnitOfWork" in content

    def test_uow_has_projects_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def projects" in content
        assert "SQLAlchemyProjectRepository" in content

    def test_uow_has_api_keys_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def api_keys" in content
        assert "SQLAlchemyApiKeyRepository" in content

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
        assert "self._projects = None" in content
        assert "self._api_keys = None" in content
        assert "self._outbox = None" in content

    def test_no_composer_imports_postgres_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "PostgresUnitOfWork" not in source, (
                f"{py_file.name} still imports PostgresUnitOfWork"
            )

    def test_all_composers_import_core_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "CoreUnitOfWork" in source, (
                f"{py_file.name} does not import CoreUnitOfWork"
            )
