from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
OBSERVABILITY_ROUTES = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "observability"
    / "presentation"
    / "http"
    / "routes.py"
)


class TestObservabilityRoutes:
    def test_routes_file_exists(self):
        assert OBSERVABILITY_ROUTES.is_file()

    def test_routes_has_observability_prefix(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/observability"' in source

    def test_routes_register_handlers(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "@router.post" in source or "@router.get" in source

    def test_routes_delegate_to_zero_argument_composers(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "list_traces_composer()" in source
        assert "get_trace_composer()" in source
        assert "app.state" not in source

    def test_routes_import_no_repository_or_domain(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "repository" not in source.lower()
        assert "from modules.observability.domain" not in source

    def test_routes_import_no_service(self):
        source = OBSERVABILITY_ROUTES.read_text(encoding="utf-8")
        assert "from modules.observability.service" not in source
