import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
METERING_CONTROLLERS_DIR = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "metering"
    / "presentation"
    / "controllers"
)


class TestMeteringControllers:
    def _controller_py_files(self) -> list[Path]:
        return [
            path
            for path in METERING_CONTROLLERS_DIR.rglob("*.py")
            if path.name != "__init__.py"
        ]

    def test_controller_files_exist(self):
        files = self._controller_py_files()
        assert files, "controller .py files must exist"

    def test_controllers_depend_on_application_interfaces(self):
        for filepath in self._controller_py_files():
            tree = ast.parse(filepath.read_text(encoding="utf-8"))
            imports_application_interface = any(
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("modules.metering.application.interfaces")
                for node in ast.walk(tree)
            )
            assert imports_application_interface, (
                f"{filepath.name} must depend on application interfaces"
            )

    def test_controllers_implement_handle_method(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "async def handle" in source or "def handle" in source, (
                f"{filepath.name} must implement handle() method"
            )

    def test_controllers_do_not_import_use_cases_directly(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "modules.metering.application.use_cases" not in source

    def test_controllers_do_not_import_service(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "from modules.metering.service" not in source, (
                f"{filepath.name} must not import from service/"
            )

    def test_controllers_do_not_import_repositories(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "repository" not in source.lower(), (
                f"{filepath.name} must not import repositories"
            )
