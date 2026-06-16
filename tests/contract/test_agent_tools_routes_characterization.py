from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROUTES = PROJECT_ROOT / "src" / "modules" / "agent" / "presentation" / "routes.py"

EXPECTED_PATH_PATTERNS = [
    "/tools",
    "/agents/{agent_id}/tools",
    "/secrets",
]

EXPECTED_METHODS = ["get", "post", "patch", "delete"]


class TestAgentToolsRoutesCharacterization:
    def test_agent_routes_file_exists(self):
        assert AGENT_ROUTES.is_file()

    def test_tools_router_defined_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "tools_router = APIRouter" in source

    def test_prefix_is_tools(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/tools"' in source

    def test_expected_paths_present_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        for pattern in EXPECTED_PATH_PATTERNS:
            assert pattern in source, f"Missing route pattern: {pattern}"

    def test_list_tools_route_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert '("tools")' in source.split('tools_list_tools')[0] or 'get("/tools")' in source

    def test_create_tool_route_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "create_tool_composer" in source

    def test_update_tool_route_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "patch(\"/tools/{tool_id}\")" in source

    def test_delete_tool_route_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "delete(\"/tools/{tool_id}\")" in source

    def test_execute_tool_route_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "execute_tool_composer" in source

    def test_list_tools_by_agent_route_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "list_tools_by_agent_composer" in source

    def test_secrets_routes_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "list_secrets_composer" in source
        assert "create_secret_composer" in source

    def test_path_compatibility(self):
        """Agent tools routes preserve legacy HTTP paths."""
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        for expected in ('"/tools"', '"/agents/', '"/secrets"'):
            assert expected in source

    def test_no_plaintext_secrets_in_responses(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "encrypted_value" not in source, (
            "Agent tools routes must not expose encrypted_value"
        )
