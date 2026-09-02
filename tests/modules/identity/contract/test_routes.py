from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
IDENTITY_ROUTES = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "identity"
    / "presentation"
    / "http"
    / "routes.py"
)


class TestIdentityRoutes:
    def test_routes_file_exists(self):
        assert IDENTITY_ROUTES.is_file(), "identity/presentation/http/routes.py must exist"

    def test_routes_has_identity_prefix(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/identity"' in source

    def test_routes_register_handlers(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert any(
            marker in source
            for marker in ("@router.get", "@router.post", "@router.patch")
        )

    def test_routes_delegate_to_composers(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "_composer(" in source or "composer(" in source

    def test_routes_import_no_repository(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower()

    def test_routes_import_no_service_layer(self):
        source = IDENTITY_ROUTES.read_text(encoding="utf-8")
        assert "from modules.identity.service" not in source
