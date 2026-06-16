from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ROUTES_FILE = PROJECT_ROOT / "src" / "modules" / "metering" / "presentation" / "routes.py"


class TestMeteringRoutes:
    def test_routes_file_exists(self):
        assert ROUTES_FILE.is_file()

    def test_router_prefix_is_metering(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'prefix="/metering"' in content

    def test_has_record_usage_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'post("/usage-events"' in content or 'post("/usage-events")' in content

    def test_has_get_project_daily_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'get("/projects/' in content

    def test_has_get_agent_daily_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'get("/agents/' in content

    def test_routes_import_from_composers(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "composers" in content

    def test_routes_use_request_adapter(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "request_adapter" in content
