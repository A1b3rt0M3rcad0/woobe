from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
IDENTITY_ROUTES = ROOT / "src" / "modules" / "identity" / "presentation" / "routes.py"


class TestIdentityRoutes:
    def test_routes_file_exists(self):
        assert IDENTITY_ROUTES.is_file(), "identity/presentation/routes.py must exist"

    def test_routes_has_identity_prefix(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/identity"' in source, (
            "Identity routes must use prefix /identity"
        )

    def test_routes_register_composers(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "@router.get" in source or "@router.post" in source or "@router.patch" in source, (
            "Routes must register HTTP handlers"
        )

    def test_routes_delegate_to_composers(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "_composer(" in source or "composer(" in source, (
            "Routes must delegate to composer functions"
        )

    def test_routes_import_no_repository(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower(), (
            "Routes must not import repositories directly"
        )

    def test_routes_import_no_domain(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "from modules.identity.domain" not in source, (
            "Routes must not import domain directly"
        )

    def test_routes_import_no_service(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "from modules.identity.service" not in source, (
            "Routes must not import from legacy service/"
        )
