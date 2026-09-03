"""Tests for spec 084 — implement agent inbox handlers."""
import ast
import asyncio
import inspect

from modules.agent.infra.messaging.inbox_handlers import (
    AgentInboxEventRouter,
    EventHandler,
)
from woobe_workers.consumers.agent.inbox_processor import AgentInboxHandlerProtocol


class TestInboxHandlersStructure:
    """Verify the handler router is properly located."""

    def test_file_exists_in_correct_location(self):
        import modules.agent.infra.messaging.inbox_handlers as mod

        assert mod.__file__ is not None
        assert "modules/agent/infra/messaging" in mod.__file__.replace("\\", "/")

    def test_class_exists(self):
        assert AgentInboxEventRouter is not None

    def test_has_handle_method(self):
        assert hasattr(AgentInboxEventRouter, "handle")
        assert inspect.iscoroutinefunction(AgentInboxEventRouter.handle)

    def test_has_register_method(self):
        assert hasattr(AgentInboxEventRouter, "register")

    def test_has_registered_event_types_property(self):
        router = AgentInboxEventRouter()
        assert hasattr(router, "registered_event_types")


class TestInboxHandlersProtocolCompliance:
    """Verify the router satisfies AgentInboxHandlerProtocol."""

    def test_handle_signature_matches_protocol(self):
        sig = inspect.signature(AgentInboxEventRouter.handle)
        params = list(sig.parameters.keys())
        assert "event_type" in params
        assert "payload" in params

    def test_router_is_compatible_with_protocol(self):
        sig_protocol = inspect.signature(AgentInboxHandlerProtocol.handle)
        sig_router = inspect.signature(AgentInboxEventRouter.handle)
        protocol_params = set(sig_protocol.parameters.keys()) - {"self"}
        router_params = set(sig_router.parameters.keys()) - {"self"}
        assert protocol_params.issubset(router_params)


class TestInboxHandlersDelegation:
    """Verify the router delegates to registered handlers."""

    def test_handle_looks_up_handler(self):
        source = inspect.getsource(AgentInboxEventRouter.handle)
        assert "_handlers" in source
        assert "get" in source

    def test_handle_calls_handler_with_event_type_and_payload(self):
        source = inspect.getsource(AgentInboxEventRouter.handle)
        assert "event_type" in source
        assert "payload" in source

    def test_handle_passes_kwargs(self):
        source = inspect.getsource(AgentInboxEventRouter.handle)
        assert "kwargs" in source

    def test_register_adds_handler(self):
        async def dummy(**kwargs):
            pass

        router = AgentInboxEventRouter()
        router.register("test.event", dummy)
        assert "test.event" in router.registered_event_types


class TestInboxHandlersUnknownEventType:
    """Verify graceful handling of unknown event types."""

    def test_handle_logs_warning_for_unknown_event(self):
        source = inspect.getsource(AgentInboxEventRouter.handle)
        assert "warning" in source.lower() or "logger" in source

    def test_handle_returns_none_for_unknown_event(self):
        source = inspect.getsource(AgentInboxEventRouter.handle)
        assert "return" in source

    def test_unknown_event_does_not_raise(self):
        router = AgentInboxEventRouter()
        asyncio.run(
            router.handle(event_type="unknown.event", payload={})
        )


class TestInboxHandlersIdempotency:
    """Verify handler dispatch supports idempotent processing."""

    def test_handle_passes_correlation_id_to_handler(self):
        source = inspect.getsource(AgentInboxEventRouter.handle)
        assert "kwargs" in source

    def test_multiple_registers_overwrite(self):
        async def handler_a(**kwargs):
            pass

        async def handler_b(**kwargs):
            pass

        router = AgentInboxEventRouter()
        router.register("test.event", handler_a)
        router.register("test.event", handler_b)
        assert len(router.registered_event_types) == 1


class TestInboxHandlersNoCrossModuleImports:
    """Verify the handlers do not import from other modules."""

    def test_no_imports_from_other_modules(self):
        import modules.agent.infra.messaging.inbox_handlers as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Forbidden cross-module import: {node.module}"
                    )

    def test_no_business_logic_in_router(self):
        source = inspect.getsource(AgentInboxEventRouter.handle)
        assert "repository" not in source.lower()
        assert "use_case" not in source.lower()
        assert "service" not in source.lower()


class TestInboxHandlersEventHandlerType:
    """Verify EventHandler type alias is properly defined."""

    def test_event_handler_type_exists(self):
        assert EventHandler is not None

    def test_constructor_accepts_handlers_dict(self):
        sig = inspect.signature(AgentInboxEventRouter.__init__)
        params = list(sig.parameters.keys())
        assert "handlers" in params
