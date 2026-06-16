from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROUTES = PROJECT_ROOT / "src" / "modules" / "agent" / "presentation" / "routes.py"
TOOLS_ROUTES = PROJECT_ROOT / "src" / "modules" / "tools" / "presentation" / "routes.py"

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

    def test_path_compatibility_with_tools_module(self):
        """Agent routes use same HTTP paths as legacy tools module."""
        tools_source = TOOLS_ROUTES.read_text(encoding="utf-8")
        agent_source = AGENT_ROUTES.read_text(encoding="utf-8")
        tools_paths = set()
        for line in tools_source.splitlines():
            line = line.strip()
            if any(line.startswith(f"@{m}.") for m in ("get", "post", "patch", "delete", "put")):
                path = line.split("(")[1].rstrip(")")
                tools_paths.add(path)
        agent_paths = set()
        for line in agent_source.splitlines():
            line = line.strip()
            if any(line.startswith(f"@{m}.") for m in ("get", "post", "patch", "delete", "put")):
                path = line.split("(")[1].rstrip(")")
                agent_paths.add(path)
        tools_method_paths = set()
        for line in tools_source.splitlines():
            line = line.strip()
            for method in ("get", "post", "patch", "delete", "put"):
                prefix = f"@{method}("
                if line.startswith(prefix):
                    path = line[len(prefix):].rstrip(")")
                    tools_method_paths.add((method, path))
        agent_method_paths = set()
        for line in agent_source.splitlines():
            line = line.strip()
            for method in ("get", "post", "patch", "delete", "put"):
                prefix = f"@{method}("
                if line.startswith(prefix):
                    path = line[len(prefix):].rstrip(")")
                    agent_method_paths.add((method, path))
        for method, path in tools_method_paths:
            assert (method, path) in agent_method_paths, (
                f"Missing agent route: {method.upper()} {path}"
            )

    def test_no_plaintext_secrets_in_responses(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "encrypted_value" not in source, (
            "Agent tools routes must not expose encrypted_value"
        )
