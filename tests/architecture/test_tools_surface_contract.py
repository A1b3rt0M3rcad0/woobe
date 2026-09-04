"""Architecture contracts for the consolidated Agent Tools HTTP surface."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROUTES = (
    PROJECT_ROOT
    / "packages"
    / "woobe-api"
    / "src"
    / "woobe_api"
    / "http"
    / "agent"
    / "routes.py"
)
AGENT_HTTP_ASSEMBLY = AGENT_ROUTES.parent / "__init__.py"
MAIN_PY = PROJECT_ROOT / "packages" / "woobe-api" / "src" / "main.py"


class TestToolsRouteRegistration:
    def test_tools_router_defined_in_agent(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "tools_router = APIRouter" in source

    def test_tools_router_prefix_is_tools(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert 'prefix="/tools"' in source

    def test_tools_router_imported_in_main(self):
        source = MAIN_PY.read_text(encoding="utf-8")
        assert "from woobe_api.http.agent import HTTP_ROUTERS as AGENT_HTTP_ROUTERS" in source

    def test_tools_router_included_in_app(self):
        source = AGENT_HTTP_ASSEMBLY.read_text(encoding="utf-8")
        assert "tools_router," in source

    def test_legacy_tools_router_not_imported(self):
        source = MAIN_PY.read_text(encoding="utf-8")
        assert "modules.tools.presentation" not in source

    def test_tools_routes_preserve_paths(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        for path_pattern in ['"/tools"', '"/agents/', '"/secrets"']:
            assert path_pattern in source, f"Missing route pattern: {path_pattern}"

    def test_tools_routes_no_encrypted_value_in_response(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        assert "encrypted_value" not in source

    def test_no_network_imports_in_schemas(self):
        schemas_path = (
            PROJECT_ROOT
            / "packages"
            / "woobe-core"
            / "src"
            / "modules"
            / "agent"
            / "presentation"
            / "schemas.py"
        )
        source = schemas_path.read_text(encoding="utf-8")
        for lib in ["httpx", "requests", "aiohttp", "urllib"]:
            assert lib not in source, f"Schema should not import network library: {lib}"
