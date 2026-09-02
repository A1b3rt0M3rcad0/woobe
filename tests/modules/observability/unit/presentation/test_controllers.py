import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OBSERVABILITY_CONTROLLERS_DIR = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "observability"
    / "presentation"
    / "controllers"
)


class TestObservabilityControllers:
    def _controller_py_files(self) -> list[Path]:
        return [
            path
            for path in OBSERVABILITY_CONTROLLERS_DIR.rglob("*.py")
            if path.name != "__init__.py"
        ]

    def test_controller_files_exist(self):
        assert self._controller_py_files()

    def test_controllers_depend_on_application_interfaces(self):
        for filepath in self._controller_py_files():
            tree = ast.parse(filepath.read_text(encoding="utf-8"))
            assert any(
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("modules.observability.application.interfaces")
                for node in ast.walk(tree)
            ), f"{filepath.name} must depend on application interfaces"

    def test_controllers_implement_handle_method(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "async def handle" in source or "def handle" in source

    def test_controllers_do_not_import_concrete_use_cases_or_repositories(self):
        for filepath in self._controller_py_files():
            source = filepath.read_text(encoding="utf-8")
            assert "modules.observability.application.use_cases" not in source
            assert "repository" not in source.lower()
