import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CONTROLLERS_DIR = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "core"
    / "presentation"
    / "controllers"
)


class TestCoreControllers:
    def _controller_files(self) -> list[Path]:
        return [
            path
            for path in CONTROLLERS_DIR.glob("*_controller.py")
            if path.name != "__init__.py"
        ]

    def test_controller_files_exist(self):
        assert self._controller_files()

    def test_controllers_depend_on_application_interfaces(self):
        for path in self._controller_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            assert any(
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("modules.core.application.interfaces")
                for node in ast.walk(tree)
            ), f"{path.name} must depend on application interfaces"

    def test_controllers_do_not_import_concrete_use_cases(self):
        for path in self._controller_files():
            source = path.read_text(encoding="utf-8")
            assert "modules.core.application.use_cases" not in source

    def test_controllers_do_not_import_repositories_or_infra(self):
        for path in self._controller_files():
            source = path.read_text(encoding="utf-8")
            assert "modules.core.infra" not in source
            assert "domain.repositories" not in source

    def test_controllers_implement_handle(self):
        for path in self._controller_files():
            assert "async def handle" in path.read_text(encoding="utf-8")
