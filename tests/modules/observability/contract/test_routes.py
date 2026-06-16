from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OBSERVABILITY_ROUTES = ROOT / "src" / "modules" / "observability" / "presentation" / "routes.py"


class TestObservabilityRoutes:
    def test_routes_file_exists(self):
        assert OBSERVABILITY_ROUTES.is_file(), "observability/presentation/routes.py must exist"

    def test_routes_has_observability_prefix(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/observability"' in source, (
            "Observability routes must use prefix /observability"
        )

    def test_routes_register_handlers(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "@router.post" in source or "@router.get" in source, (
            "Routes must register HTTP handlers"
        )

    def test_routes_delegate_to_composers(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "_composer(" in source, (
            "Routes must delegate to composer functions"
        )

    def test_routes_import_no_repository(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower(), (
            "Routes must not import repositories directly"
        )

    def test_routes_import_no_domain(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "from modules.observability.domain" not in source, (
            "Routes must not import domain directly"
        )

    def test_routes_import_no_service(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "from modules.observability.service" not in source, (
            "Routes must not import from legacy service/"
        )
