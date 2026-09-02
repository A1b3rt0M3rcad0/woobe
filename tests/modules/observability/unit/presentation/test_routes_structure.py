from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ROUTES_FILE = (
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
        assert ROUTES_FILE.is_file()

    def test_router_surface(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'prefix="/observability"' in content
        assert 'get("/traces")' in content
        assert 'post("/traces"' in content
        assert 'get("/traces/{trace_id}")' in content
        assert 'post("/traces/{trace_id}/events"' in content
        assert "composition.composers" in content
        assert "request_adapter" in content
        assert "app.state" not in content
