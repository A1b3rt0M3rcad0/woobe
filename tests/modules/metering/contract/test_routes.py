from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
METERING_ROUTES = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "metering"
    / "presentation"
    / "http"
    / "routes.py"
)


class TestMeteringRoutes:
    def test_routes_file_exists(self):
        assert METERING_ROUTES.is_file(), "metering/presentation/http/routes.py must exist"

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
        assert "_composer()" in source, (
            "Routes must delegate to zero-argument composer functions"
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

    def test_routes_do_not_use_app_state_for_dependency_injection(self):
        source = METERING_ROUTES.read_text(encoding="utf-8")
        assert "request.app.state" not in source
