from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
IDENTITY_ROOT = (
    PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "identity"
)
ROUTES_FILE = IDENTITY_ROOT / "presentation" / "http" / "routes.py"
CONTROLLERS_DIR = IDENTITY_ROOT / "presentation" / "controllers"


class TestIdentityRoutes:
    def test_routes_file_exists(self):
        assert ROUTES_FILE.is_file()

    def test_routes_has_router(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "router" in content

    def test_routes_imports_composers(self):
        source = ROUTES_FILE.read_text(encoding="utf-8")
        assert "_composer" in source, "Routes must import composer functions"

    def test_all_controllers_import_use_cases(self):
        for py_file in CONTROLLERS_DIR.iterdir():
            if py_file.suffix != ".py" or py_file.name.startswith("__"):
                continue
            source = py_file.read_text(encoding="utf-8")
            assert "from modules.identity.application.use_cases" in source, (
                f"{py_file.name} must import from application/use_cases"
            )
