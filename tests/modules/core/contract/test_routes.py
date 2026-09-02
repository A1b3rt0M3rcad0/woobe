from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CORE_ROUTES = (
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
        assert CORE_ROUTES.is_file(), "core/presentation/http/routes.py must exist"

    def test_routes_has_core_prefix(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/core"' in source

    def test_routes_register_handlers(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert any(
            marker in source
            for marker in ("@router.get", "@router.post", "@router.patch")
        )

    def test_routes_delegate_to_zero_argument_composers(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "_composer()" in source
        assert "request.app.state" not in source

    def test_routes_import_no_repository_or_domain(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower()
        assert "from modules.core.domain" not in source

    def test_routes_import_no_service(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        assert "from modules.core.service" not in source
