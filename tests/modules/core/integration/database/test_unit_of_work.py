import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CORE_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core"
UOW_FILE = CORE_DIR / "infra" / "database" / "unit_of_work.py"
COMPOSERS_DIR = CORE_DIR / "composition" / "composers"


class TestCoreUnitOfWork:
    def test_uow_file_exists(self):
        assert UOW_FILE.is_file(), f"CoreUnitOfWork file missing: {UOW_FILE}"

    def test_uow_class_name(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "class CoreUnitOfWork" in content

    def test_uow_accepts_async_engine(self):
        tree = ast.parse(UOW_FILE.read_text(encoding="utf-8"))
        cls = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CoreUnitOfWork"
        )
        init = next(
            node
            for node in cls.body
            if isinstance(node, ast.FunctionDef) and node.name == "__init__"
        )
        args = [arg for arg in init.args.args if arg.arg != "self"]
        assert [arg.arg for arg in args] == ["engine"]
        assert ast.unparse(args[0].annotation) == "AsyncEngine"

    def test_uow_does_not_own_repositories(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "Repository" not in content
        assert "OutboxEventWriter" not in content

    def test_uow_exposes_only_session_property(self):
        tree = ast.parse(UOW_FILE.read_text(encoding="utf-8"))
        cls = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CoreUnitOfWork"
        )
        properties = {
            node.name
            for node in cls.body
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(decorator, ast.Name) and decorator.id == "property"
                for decorator in node.decorator_list
            )
        }
        assert properties == {"session"}

    def test_uow_has_transaction_lifecycle(self):
        content = UOW_FILE.read_text(encoding="utf-8")
        assert "async def commit" in content
        assert "async def rollback" in content
        assert "__aenter__" in content
        assert "__aexit__" in content

    def test_all_composers_use_core_unit_of_work(self):
        py_files = [
            path
            for path in sorted(COMPOSERS_DIR.iterdir())
            if path.suffix == ".py" and not path.name.startswith("__")
        ]
        assert py_files
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            assert "CoreUnitOfWork" in source
            assert "session_factory" not in source
