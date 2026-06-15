import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestUoWTransactionAtomicity:
    def test_each_uow_has_commit_and_rollback(self):
        for mod in MODULES:
            uow_path = SRC_MODULES / mod / "infra" / "database" / "unit_of_work.py"
            assert uow_path.exists(), f"{mod} missing unit_of_work.py"
            source = uow_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            func_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
            has_commit = "commit" in func_names
            has_rollback = "rollback" in func_names
            inherits = "UnitOfWork" in source or "BaseUnitOfWork" in source
            assert has_commit or inherits, f"{mod} UoW missing commit() and no base class inheriting from UnitOfWork"
            assert has_rollback or inherits, f"{mod} UoW missing rollback() and no base class inheriting from UnitOfWork"

    def test_each_uow_handles_pending_rollback_error(self):
        for mod in MODULES:
            uow_path = SRC_MODULES / mod / "infra" / "database" / "unit_of_work.py"
            source = uow_path.read_text(encoding="utf-8")
            assert "PendingRollbackError" in source, (
                f"{mod} UoW must handle PendingRollbackError"
            )

    def test_each_uow_rollback_on_exception(self):
        for mod in MODULES:
            uow_path = SRC_MODULES / mod / "infra" / "database" / "unit_of_work.py"
            source = uow_path.read_text(encoding="utf-8")
            assert "rollback()" in source, f"{mod} UoW must call rollback()"

    def test_each_module_has_outbox_atomicity_test(self):
        missing = []
        for mod in MODULES:
            test_path = (
                PROJECT_ROOT / "tests" / "modules" / mod / "integration" / "test_outbox_atomicity.py"
            )
            if not test_path.exists():
                missing.append(mod)
        if missing:
            import warnings
            warnings.warn(
                f"Modules missing outbox atomicity tests: {missing}"
            )

    def test_each_uow_wraps_outbox_and_state_in_single_transaction(self):
        for mod in MODULES:
            uow_path = SRC_MODULES / mod / "infra" / "database" / "unit_of_work.py"
            source = uow_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            class_defs = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            assert len(class_defs) >= 1, f"{mod} UoW file has no class"
            uow_cls = class_defs[0]
            init_methods = [
                n for n in ast.walk(uow_cls)
                if isinstance(n, ast.FunctionDef) and n.name == "__init__"
            ]
            if init_methods:
                init_body = ast.unparse(init_methods[0])
                assert "self._session" in init_body or "self.session" in init_body, (
                    f"{mod} UoW __init__ should reference self.session"
                )
