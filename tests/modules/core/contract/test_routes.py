from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CORE_ROUTES = ROOT / "src" / "modules" / "core" / "presentation" / "routes.py"


class TestCoreRoutes:
    def test_routes_file_exists(self):
        assert CORE_ROUTES.is_file(), "core/presentation/routes.py must exist"

    def test_routes_has_core_prefix(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/core"' in source, (
            "Core routes must use prefix /core"
        )

    def test_routes_register_composers(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "@router.get" in source or "@router.post" in source or "@router.patch" in source, (
            "Routes must register HTTP handlers"
        )

    def test_routes_delegate_to_composers(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "_composer(" in source or "composer(" in source, (
            "Routes must delegate to composer functions"
        )

    def test_routes_import_no_repository(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower(), (
            "Routes must not import repositories directly"
        )

    def test_routes_import_no_domain(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "from modules.core.domain" not in source, (
            "Routes must not import domain directly"
        )

    def test_routes_import_no_service(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "from modules.core.service" not in source, (
            "Routes must not import from legacy service/"
        )
