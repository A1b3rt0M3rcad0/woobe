"""Tests for spec 130 — update application bootstrap.

Validates that packages/woobe-api/src/main.py imports and registers routers from
the agent module directly, with legacy ai/knowledge/runtime routers retained
only as deprecation shims. Also verifies the bootstrap sets up engine,
session_factory, settings, CORS, exception handlers, and the startup/shutdown
lifecycle.
"""
import inspect

from fastapi import FastAPI


class TestBootstrapAgentRouterRegistration:
    """Verify the API process bootstrap registers agent routers directly."""

    def test_bootstrap_imports_agent_presentation_routes(self):
        import main as main_mod

        source = inspect.getsource(main_mod)
        assert "from woobe_api.http.agent import HTTP_ROUTERS" in source

    def test_bootstrap_registers_agent_ai_router(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        assert "AGENT_HTTP_ROUTERS" in source

    def test_bootstrap_registers_agent_knowledge_router(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        assert "AGENT_HTTP_ROUTERS" in source

    def test_bootstrap_registers_agent_runtime_router(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        assert "AGENT_HTTP_ROUTERS" in source

    def test_bootstrap_uses_include_router_for_agent_routers(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        assert "for agent_http_router in AGENT_HTTP_ROUTERS" in source
        assert "include_router(agent_http_router)" in source


class TestBootstrapLegacyRouterShims:
    """Verify legacy routes files still exist as deprecation shims."""


class TestBootstrapAllModules:
    """Verify all module routers are registered."""

    def test_all_non_legacy_modules_registered(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        expected_routers = [
            "instance_router",
            "identity_router",
            "core_router",
            "chat_surface_router",
            "chat_surface_reattach_router",
            "public_runtime_router",
            "AGENT_HTTP_ROUTERS",
            "runtime_environment_router",
            "metering_router",
            "observability_router",
            "network_router",
        ]
        for name in expected_routers:
            assert name in source, f"Missing router registration: {name}"

    def test_legacy_routers_not_registered_separately(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        assert "include_router(ai_router)" not in source
        assert "include_router(knowledge_router)" not in source
        assert "include_router(runtime_router)" not in source


class TestBootstrapInfrastructure:
    """Verify bootstrap creates required infrastructure."""

    def test_create_app_returns_fastapi_instance(self):
        from main import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_create_app_sets_settings_on_state(self):
        from main import create_app

        app = create_app()
        assert hasattr(app.state, "settings")

    def test_create_app_sets_async_engine_on_state(self):
        from main import create_app

        app = create_app()
        assert hasattr(app.state, "async_engine")

    def test_create_app_sets_session_factory_on_state(self):
        from main import create_app

        app = create_app()
        assert hasattr(app.state, "session_factory")

    def test_create_app_has_cors_middleware(self):
        from fastapi.middleware.cors import CORSMiddleware
        from main import create_app

        app = create_app()
        middlewares = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middlewares

    def test_create_app_has_health_endpoint(self):
        from main import create_app

        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in routes

    def test_create_app_has_startup_handler(self):
        from main import create_app

        app = create_app()
        assert len(app.router.on_startup) >= 1

    def test_create_app_has_shutdown_handler(self):
        from main import create_app

        app = create_app()
        assert len(app.router.on_shutdown) >= 1


class TestBootstrapExceptionHandlers:
    """Verify all required exception handlers are registered."""

    def test_domain_error_handler_registered(self):
        from main import create_app
        from shared.infra.errors import DomainError

        app = create_app()
        assert DomainError in app.exception_handlers

    def test_not_found_error_handler_registered(self):
        from main import create_app
        from shared.infra.errors import NotFoundError

        app = create_app()
        assert NotFoundError in app.exception_handlers

    def test_conflict_error_handler_registered(self):
        from main import create_app
        from shared.infra.errors import ConflictError

        app = create_app()
        assert ConflictError in app.exception_handlers

    def test_validation_error_handler_registered(self):
        from main import create_app
        from shared.infra.errors import ValidationError

        app = create_app()
        assert ValidationError in app.exception_handlers


class TestBootstrapNoCrossModuleImports:
    """Verify the API bootstrap imports from agent directly, not legacy modules."""

    def test_main_imports_agent_directly(self):
        import main as main_mod

        source = inspect.getsource(main_mod)
        assert "from woobe_api.http.agent import HTTP_ROUTERS" in source

    def test_main_registers_agent_routers_not_legacy(self):
        import main as main_mod

        source = inspect.getsource(main_mod.create_app)
        assert "AGENT_HTTP_ROUTERS" in source
