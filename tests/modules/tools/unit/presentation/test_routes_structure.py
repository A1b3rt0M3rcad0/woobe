from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
ROUTES_FILE = PROJECT_ROOT / "src" / "modules" / "tools" / "presentation" / "routes.py"


class TestToolsRoutes:
    def test_routes_file_exists(self):
        assert ROUTES_FILE.is_file()

    def test_router_prefix_is_tools(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'prefix="/tools"' in content or 'prefix = "/tools"' in content

    def test_has_create_tool_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'post("/tools"' in content or 'post("/tools")' in content

    def test_has_list_tools_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'get("/tools"' in content or 'get("/tools")' in content

    def test_has_create_secret_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'post("/secrets"' in content or 'post("/secrets")' in content

    def test_has_list_secrets_route(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert 'get("/secrets"' in content or 'get("/secrets")' in content

    def test_routes_import_from_composers(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "composers" in content

    def test_routes_use_request_adapter(self):
        content = ROUTES_FILE.read_text(encoding="utf-8")
        assert "request_adapter" in content
