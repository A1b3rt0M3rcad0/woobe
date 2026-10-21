from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent"
COMPOSERS_DIR = AGENT_DIR / "composition" / "composers"
CONTROLLERS_DIR = AGENT_DIR / "presentation" / "controllers"

FORBIDDEN_CONTROLLER_IMPORTS = (
    "modules.agent.application.use_cases",
    "modules.agent.infra",
    "modules.agent.composition",
    "shared.infra",
    "woobe_workers",
    "fastapi",
    "starlette",
    "sqlalchemy",
)
FORBIDDEN_COMPOSER_IMPORTS = (
    "modules.agent.presentation.routes",
    "woobe_api",
    "fastapi",
    "starlette",
    "sqlalchemy",
    "asyncpg",
)


def _get_import_from(file_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


class TestNormalizeAgentComposersAndControllers:
    def test_composers_directory_exists(self):
        assert COMPOSERS_DIR.is_dir()

    def test_composers_have_multiple_files(self):
        py_files = [f for f in COMPOSERS_DIR.iterdir() if f.suffix == ".py" and not f.name.startswith("__")]
        assert len(py_files) >= 40, f"Expected 40+ composer files, found {len(py_files)}"

    def test_controllers_directory_exists(self):
        assert CONTROLLERS_DIR.is_dir()

    def test_controllers_have_multiple_files(self):
        py_files = [f for f in CONTROLLERS_DIR.iterdir() if f.suffix == ".py" and not f.name.startswith("__")]
        assert len(py_files) >= 30, f"Expected 30+ controller files, found {len(py_files)}"

    def test_controllers_stay_inside_the_presentation_boundary(self):
        for py_file in CONTROLLERS_DIR.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            imports = _get_import_from(py_file)
            for imp in imports:
                for forbidden in FORBIDDEN_CONTROLLER_IMPORTS:
                    assert not imp.startswith(forbidden), (
                        f"Controller {py_file.relative_to(PROJECT_ROOT)} crosses its boundary: {imp}"
                    )

    def test_composers_stay_out_of_http_and_framework_layers(self):
        for py_file in COMPOSERS_DIR.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            imports = _get_import_from(py_file)
            for imp in imports:
                for forbidden in FORBIDDEN_COMPOSER_IMPORTS:
                    assert not imp.startswith(forbidden), (
                        f"Composer {py_file.relative_to(PROJECT_ROOT)} crosses its boundary: {imp}"
                    )

    def test_composers_import_from_use_cases_package(self):
        composers_using_package = 0
        for py_file in COMPOSERS_DIR.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            if "from modules.agent.application.use_cases import" in source:
                composers_using_package += 1
        assert composers_using_package >= 40, f"Expected 40+ composers using use_cases package, found {composers_using_package}"

    def test_controllers_import_from_dtos_package(self):
        controllers_using_package = 0
        for py_file in CONTROLLERS_DIR.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            if "from modules.agent.application.dtos import" in source:
                controllers_using_package += 1
        assert controllers_using_package >= 25, f"Expected 25+ controllers using dtos package, found {controllers_using_package}"

    def test_controller_handle_method_returns_response(self):
        assert (CONTROLLERS_DIR / "create_agent_controller.py").exists()
        source = (CONTROLLERS_DIR / "create_agent_controller.py").read_text(encoding="utf-8")
        assert "async def handle" in source
        assert "OperationResult" in source

    def test_composer_wires_use_case_and_controller(self):
        composer = COMPOSERS_DIR / "create_agent_composer.py"
        assert composer.exists()
        source = composer.read_text(encoding="utf-8")
        assert "use_case" in source
        assert "controller" in source
        assert "TransactionalHandler" in source
