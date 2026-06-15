from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BILLING_ROUTES = ROOT / "src" / "modules" / "billing" / "presentation" / "routes.py"


class TestBillingRoutes:
    def test_routes_file_exists(self):
        assert BILLING_ROUTES.is_file(), "billing/presentation/routes.py must exist"

    def test_routes_has_billing_prefix(self):
        source = BILLING_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/billing"' in source, (
            "Billing routes must use prefix /billing"
        )

    def test_routes_register_handlers(self):
        source = BILLING_ROUTES.read_text(encoding="utf-8")
        assert "@router.post" in source or "@router.get" in source, (
            "Routes must register HTTP handlers"
        )

    def test_routes_delegate_to_composers(self):
        source = BILLING_ROUTES.read_text(encoding="utf-8")
        assert "_composer(" in source, (
            "Routes must delegate to composer functions"
        )

    def test_routes_import_no_repository(self):
        source = BILLING_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower(), (
            "Routes must not import repositories directly"
        )

    def test_routes_import_no_domain(self):
        source = BILLING_ROUTES.read_text(encoding="utf-8")
        assert "from modules.billing.domain" not in source, (
            "Routes must not import domain directly"
        )

    def test_routes_import_no_service(self):
        source = BILLING_ROUTES.read_text(encoding="utf-8")
        assert "from modules.billing.service" not in source, (
            "Routes must not import from legacy service/"
        )
