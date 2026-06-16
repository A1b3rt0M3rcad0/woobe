from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_ROUTES = PROJECT_ROOT / "src" / "modules" / "tools" / "presentation" / "routes.py"

EXPECTED_PATH_PATTERNS = [
    "/tools",
    "/agents/{agent_id}/tools",
    "/secrets",
]

EXPECTED_METHODS = ["get", "post", "patch", "delete"]


class TestToolsRoutesCharacterization:
    def test_routes_file_exists(self):
        assert TOOLS_ROUTES.is_file()

    def test_router_defined(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "router = APIRouter" in source

    def test_prefix_is_tools(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/tools"' in source or 'prefix = "/tools"' in source

    def test_expected_paths_present(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        for pattern in EXPECTED_PATH_PATTERNS:
            assert pattern in source, f"Missing route pattern: {pattern}"

    def test_list_tools_route(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.get(\"/tools\")" in source

    def test_create_tool_route(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.post(\"/tools\")" in source

    def test_update_tool_route(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.patch(\"/tools/{tool_id}\")" in source

    def test_delete_tool_route(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.delete(\"/tools/{tool_id}\")" in source

    def test_execute_tool_route(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.post(\"/tools/execute\")" in source

    def test_list_tools_by_agent_route(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.get(\"/agents/{agent_id}/tools\")" in source

    def test_secrets_routes(self):
        source = TOOLS_ROUTES.read_text(encoding="utf-8")
        assert "@router.get(\"/secrets\")" in source
        assert "@router.post(\"/secrets\")" in source

    def test_route_registration_in_main(self):
        main_path = PROJECT_ROOT / "src" / "main.py"
        source = main_path.read_text(encoding="utf-8")
        assert "tools" in source
