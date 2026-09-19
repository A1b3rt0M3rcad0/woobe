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
CORE_ROUTES = (
    PROJECT_ROOT
    / "packages"
    / "woobe-api"
    / "src"
    / "woobe_api"
    / "http"
    / "core"
    / "routes.py"
)


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

    def test_project_environment_tool_test_requires_project_access(self):
        source = AGENT_ROUTES.read_text(encoding="utf-8")
        test_route = source.split('@tools_router.post("/tools/test")', 1)[1].split(
            '@tools_router.post("/tools/execute")',
            1,
        )[0]
        assert "build_project_access_service().require_project_access" in test_route
        assert 'payload.get("project_id")' in test_route


    def test_project_environment_list_exposes_tool_dependencies(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        list_route = source.split(
            '@router.get("/projects/{project_id}/environment-keys")',
            1,
        )[1].split(
            '@router.put("/projects/{project_id}/environment-keys/{key}")',
            1,
        )[0]
        assert "_project_environment_tool_usage(request)" in list_route
        assert 'item["used_by_tools"]' in list_route

    def test_project_environment_delete_blocks_referenced_keys(self):
        source = CORE_ROUTES.read_text(encoding="utf-8")
        delete_route = source.split(
            '@router.delete("/projects/{project_id}/environment-keys/{key}")',
            1,
        )[1].split(
            '@router.post("/projects/{project_id}/api-keys")',
            1,
        )[0]
        assert "_project_environment_tool_usage(request)" in delete_route
        assert "raise ConflictError" in delete_route
        assert "Edit or delete those Tools before removing this key." in delete_route

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
