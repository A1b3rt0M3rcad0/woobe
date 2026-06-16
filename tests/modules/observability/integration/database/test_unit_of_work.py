from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
OBSERVABILITY_DIR = PROJECT_ROOT / "src" / "modules" / "observability"
UOW_FILE = OBSERVABILITY_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = OBSERVABILITY_DIR / "application" / "composers"


class TestObservabilityUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file(), f"ObservabilityUnitOfWork file missing: {UOW_FILE}"

    def test_uow_class_name(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityUnitOfWork" in content

    def test_uow_extends_unit_of_work(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "UnitOfWork" in content

    def test_uow_has_traces_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def traces" in content
        assert "SQLAlchemyTraceRepository" in content

    def test_uow_has_trace_events_property(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "def trace_events" in content
        assert "SQLAlchemyTraceEventRepository" in content

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
        assert "self._traces = None" in content
        assert "self._trace_events = None" in content
        assert "self._outbox = None" in content

    def test_no_composer_imports_postgres_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "PostgresUnitOfWork" not in source, (
                f"{py_file.name} still imports PostgresUnitOfWork"
            )

    def test_all_composers_import_observability_unit_of_work(self):
        for py_file in sorted(COMPOSERS_DIR.iterdir()):
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "ObservabilityUnitOfWork" in source, (
                f"{py_file.name} does not import ObservabilityUnitOfWork"
            )
