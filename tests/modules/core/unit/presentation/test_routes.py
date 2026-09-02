from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ROUTES_FILE = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "core"
    / "presentation"
    / "http"
    / "routes.py"
)


class TestCoreRoutes:
    def test_routes_file_exists(self):
        assert ROUTES_FILE.is_file()

    def test_routes_has_router(self):
        assert "router" in ROUTES_FILE.read_text(encoding="utf-8")

    def test_routes_invoke_zero_argument_composers(self):
        source = ROUTES_FILE.read_text(encoding="utf-8")
        assert "_composer()" in source
        assert "app.state" not in source
