from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
METERING_ROUTES = ROOT / "src" / "modules" / "metering" / "presentation" / "routes.py"


class TestMeteringRoutes:
    def test_routes_file_exists(self):
        assert METERING_ROUTES.is_file(), "metering/presentation/routes.py must exist"

    def test_routes_has_metering_prefix(self):
        source = METERING_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/metering"' in source, (
            "Metering routes must use prefix /metering"
        )

    def test_routes_register_handlers(self):
        source = METERING_ROUTES.read_text(encoding="utf-8")
        assert "@router.post" in source or "@router.get" in source, (
            "Routes must register HTTP handlers"
        )

    def test_routes_delegate_to_composers(self):
        source = METERING_ROUTES.read_text(encoding="utf-8")
        assert "_composer(" in source, (
            "Routes must delegate to composer functions"
        )

    def test_routes_import_no_repository(self):
        source = METERING_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower(), (
            "Routes must not import repositories directly"
        )

    def test_routes_import_no_domain(self):
        source = METERING_ROUTES.read_text(encoding="utf-8")
        assert "from modules.metering.domain" not in source, (
            "Routes must not import domain directly"
        )

    def test_routes_import_no_service(self):
        source = METERING_ROUTES.read_text(encoding="utf-8")
        assert "from modules.metering.service" not in source, (
            "Routes must not import from legacy service/"
        )
