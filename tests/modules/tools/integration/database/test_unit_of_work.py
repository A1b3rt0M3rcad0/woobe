from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
TOOLS_DIR = PROJECT_ROOT / "src" / "modules" / "tools"
UOW_FILE = TOOLS_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = TOOLS_DIR / "application" / "composers"


class TestToolsUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file(), f"ToolsUnitOfWork file missing: {UOW_FILE}"

    def test_uow_class_name(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class ToolsUnitOfWork" in content

    def test_uow_extends_unit_of_work(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "UnitOfWork" in content

    def test_uow_has_tools_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def tools" in content
        assert "SQLAlchemyToolRepository" in content

    def test_uow_has_secrets_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def secrets" in content
        assert "SQLAlchemySecretRepository" in content

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
        assert "self._tools = None" in content
        assert "self._secrets = None" in content
        assert "self._outbox = None" in content

    def test_no_composer_imports_postgres_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "PostgresUnitOfWork" not in source, (
                f"{py_file.name} still imports PostgresUnitOfWork"
            )

    def test_all_composers_import_tools_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "ToolsUnitOfWork" in source, (
                f"{py_file.name} does not import ToolsUnitOfWork"
            )
