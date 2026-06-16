from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ROUTES_FILE = PROJECT_ROOT / "src" / "modules" / "observability" / "presentation" / "routes.py"


class TestObservabilityRoutes:
    def test_routes_file_exists(self):
        assert ROUTES_FILE.is_file()

    def test_router_prefix_is_observability(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'prefix="/observability"' in content

    def test_has_list_traces_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'get("/traces"' in content or 'get("/traces")' in content

    def test_has_create_trace_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'post("/traces"' in content or 'post("/traces")' in content

    def test_has_get_trace_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'get("/traces/' in content

    def test_has_add_trace_event_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'post("/traces/' in content or 'post("/traces/{trace_id}/events"' in content

    def test_routes_import_from_composers(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "composers" in content

    def test_routes_use_request_adapter(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "request_adapter" in content
