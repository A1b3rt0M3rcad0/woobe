from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TOOLS_ROUTES = ROOT / "src" / "modules" / "tools" / "presentation" / "routes.py"


class TestToolsRoutes:
    def test_routes_file_exists(self):
        assert TOOLS_ROUTES.is_file(), "tools/presentation/routes.py must exist"

    def test_routes_has_tools_prefix(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/tools"' in source, (
            "Tools routes must use prefix /tools"
        )

    def test_routes_register_composers(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.get" in source or "@router.post" in source or "@router.patch" in source or "@router.delete" in source, (
            "Routes must register HTTP handlers"
        )

    def test_routes_delegate_to_composers(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "_composer(" in source or "composer(" in source, (
            "Routes must delegate to composer functions"
        )

    def test_routes_import_no_repository(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower(), (
            "Routes must not import repositories directly"
        )

    def test_routes_import_no_domain(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "from modules.tools.domain" not in source, (
            "Routes must not import domain directly"
        )

    def test_routes_import_no_service(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "from modules.tools.service" not in source, (
            "Routes must not import from legacy service/"
        )

    def test_routes_imports_from_application_composers(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "from modules.tools.application.composers" in source, (
            "Routes must import from application/composers"
        )
