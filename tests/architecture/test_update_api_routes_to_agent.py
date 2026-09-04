"""Tests for spec 131 — update API routes to agent.

Validates that the agent presentation routes module exports a consolidated
`agent_router` with prefix `/agent`, that legacy prefix routers remain as
deprecation shims, and that no forbidden cross-module imports exist.
"""
import importlib
import inspect

from fastapi import APIRouter


class TestAgentRoutesSuccess:
    """Verify agent routes module exports consolidated agent_router."""

    def test_agent_routes_module_exports_agent_router(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        assert hasattr(mod, "agent_router"), (
            "agent/presentation/routes.py must export 'agent_router'"
        )

    def test_agent_router_has_agent_prefix(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        assert isinstance(mod.agent_router, APIRouter)
        assert mod.agent_router.prefix == "/agent", (
            "agent_router prefix must be /agent"
        )

    def test_agent_router_has_agent_tag(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        assert "agent" in mod.agent_router.tags, (
            "agent_router must have 'agent' tag"
        )

    def test_agent_router_includes_legacy_routers(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        legacy_names = {r.name for r in mod.agent_router.routes if hasattr(r, "name")}
        has_ai = "ai" in str(legacy_names).lower() or any(
            "/ai/" in getattr(r, "path", "") for r in mod.agent_router.routes
        )
        has_knowledge = "knowledge" in str(legacy_names).lower() or any(
            "/knowledge/" in getattr(r, "path", "") for r in mod.agent_router.routes
        )
        has_runtime = "runtime" in str(legacy_names).lower() or any(
            "/runtime/" in getattr(r, "path", "") for r in mod.agent_router.routes
        )
        assert has_ai or has_knowledge or has_runtime, (
            "agent_router should include legacy sub-routers"
        )

    def test_main_registers_agent_router(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        assert "for agent_http_router in AGENT_HTTP_ROUTERS" in source
        assert "include_router(agent_http_router)" in source

    def test_main_imports_agent_router(self):
        import main as main_mod

        source = inspect.getsource(main_mod)
        assert "from woobe_api.http.agent import HTTP_ROUTERS as AGENT_HTTP_ROUTERS" in source


class TestAgentRoutesNoForbiddenDependency:
    """Verify agent routes have no forbidden cross-module imports."""

    def test_agent_routes_has_no_legacy_module_imports(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        source = inspect.getsource(mod)
        forbidden = [
            "from modules.ai.",
            "from modules.knowledge.",
            "from modules.runtime.",
            "import modules.ai",
            "import modules.knowledge",
            "import modules.runtime",
        ]
        for pattern in forbidden:
            assert pattern not in source, (
                f"agent/presentation/routes.py must not import {pattern}"
            )

    def test_agent_routes_only_imports_from_agent_and_shared(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        source = inspect.getsource(mod)
        import_lines = [
            line for line in source.splitlines()
            if line.strip().startswith(("from ", "import "))
        ]
        for line in import_lines:
            if "modules." in line:

                assert "modules.agent." in line or "shared." in line or "fastapi" in line.lower(), (
                    f"Unexpected import in agent routes: {line.strip()}"
                )


class TestAgentRoutesLegacyCompatibility:
    """Verify legacy prefix routers remain as deprecation shims."""

    def test_legacy_ai_router_still_exists(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        assert hasattr(mod, "router"), (
            "Legacy /ai prefix router must still exist"
        )
        assert isinstance(mod.router, APIRouter)
        assert "/ai" in (mod.router.prefix or "")

    def test_legacy_knowledge_router_still_exists(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        assert hasattr(mod, "knowledge_router"), (
            "Legacy /knowledge prefix router must still exist"
        )
        assert isinstance(mod.knowledge_router, APIRouter)
        assert "/knowledge" in (mod.knowledge_router.prefix or "")

    def test_legacy_runtime_router_still_exists(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        assert hasattr(mod, "runtime_router"), (
            "Legacy /runtime prefix router must still exist"
        )
        assert isinstance(mod.runtime_router, APIRouter)
        assert "/runtime" in (mod.runtime_router.prefix or "")

    def test_legacy_routers_have_agent_tag(self):
        mod = importlib.import_module("woobe_api.http.agent.routes")
        assert "agent" in mod.router.tags, (
            "Legacy /ai router should include 'agent' tag"
        )
        assert "agent" in mod.knowledge_router.tags, (
            "Legacy /knowledge router should include 'agent' tag"
        )
        assert "agent" in mod.runtime_router.tags, (
            "Legacy /runtime router should include 'agent' tag"
        )

    def test_main_still_registers_legacy_routers(self):
        mod = importlib.import_module("woobe_api.http.agent")
        routes = importlib.import_module("woobe_api.http.agent.routes")

        assert routes.router in mod.HTTP_ROUTERS
        assert routes.knowledge_router in mod.HTTP_ROUTERS
        assert routes.runtime_router in mod.HTTP_ROUTERS

    def test_main_registers_agent_router_before_legacy(self):
        mod = importlib.import_module("woobe_api.http.agent")
        routes = importlib.import_module("woobe_api.http.agent.routes")

        assert mod.HTTP_ROUTERS.index(routes.agent_router) < mod.HTTP_ROUTERS.index(
            routes.router
        )
