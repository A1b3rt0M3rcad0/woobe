from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
OBSERVABILITY_DIR = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "observability"
)
UOW_FILE = OBSERVABILITY_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = OBSERVABILITY_DIR / "composition" / "composers"


class TestObservabilityUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file()

    def test_uow_owns_only_transaction_lifecycle(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class ObservabilityUnitOfWork" in content
        assert "AsyncEngine" in content
        assert "async_sessionmaker" in content
        assert "async def commit" in content
        assert "async def rollback" in content
        assert "__aenter__" in content
        assert "__aexit__" in content
        assert "def traces" not in content
        assert "def trace_events" not in content
        assert "def outbox" not in content
        assert "SQLAlchemyTraceRepository" not in content

    def test_composers_are_top_level_and_build_explicit_repositories(self):
        py_files = [
            path
            for path in COMPOSERS_DIR.iterdir()
            if path.suffix == ".py" and not path.name.startswith("__")
        ]
        assert py_files
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            assert "ObservabilityUnitOfWork(DATABASE_ENGINE)" in source
            assert "session_factory" not in source
