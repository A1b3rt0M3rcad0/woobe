from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ROUTES_FILE = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core" / "presentation" / "routes.py"
CONTROLLERS_DIR = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core" / "presentation" / "controllers"


class TestCoreRoutes:
    def test_routes_file_exists(self):
        assert ROUTES_FILE.is_file()

    def test_routes_has_router(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "router" in content

    def test_routes_imports_composers(self):
        source = ROUTES_FILE.read_text(encoding="utf-8")
        assert "_composer" in source

    def test_all_controllers_import_use_cases(self):
        for py_file in CONTROLLERS_DIR.iterdir():
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "from modules.core.application.use_cases" in source, (
                f"{py_file.name} must import from application/use_cases"
            )
