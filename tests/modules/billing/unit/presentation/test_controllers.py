import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BILLING_CONTROLLERS_DIR = ROOT / "src" / "editions" / "cloud" / "billing" / "presentation" / "controllers"


class TestBillingControllers:
    def _controller_py_files(self) -> list[Path]:
        return [
            p for p in BILLING_CONTROLLERS_DIR.rglob("*.py")
            if p.name != "__init__.py"
        ]

    def test_controller_files_exist(self):
        files = self._controller_py_files()
        assert len(files) > 0, "controller .py files must exist"

    def test_controllers_import_from_application_use_cases(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports_app_use_cases = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "application.use_cases" in node.module:
                        imports_app_use_cases = True
            assert imports_app_use_cases, (
                f"{filepath.name} must import from application.use_cases"
            )

    def test_controllers_implement_handle_method(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "async def handle" in source or "def handle" in source, (
                f"{filepath.name} must implement handle() method"
            )

    def test_controllers_do_not_import_service(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "editions.cloud.billing.service" not in source, (
                f"{filepath.name} must not import from service/"
            )
            assert "modules.billing" not in source, (
                f"{filepath.name} must not import the removed Billing compatibility namespace"
            )

    def test_controllers_do_not_import_repositories(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "repository" not in source.lower(), (
                f"{filepath.name} must not import repositories"
            )
