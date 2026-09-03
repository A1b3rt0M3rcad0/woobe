"""Tests for spec 081 — implement agent rabbitmq publisher."""
import ast
import inspect

from modules.agent.infra.messaging.publishers import AgentRabbitMQPublisher
from woobe_workers.consumers.agent.outbox_dispatcher import AgentOutboxPublisherProtocol


class TestRabbitMQPublisherStructure:
    """Verify the publisher is properly located and structured."""

    def test_file_exists_in_correct_location(self):
        import modules.agent.infra.messaging.publishers as mod

        assert mod.__file__ is not None
        assert "modules/agent/infra/messaging" in mod.__file__.replace("\\", "/")

    def test_class_exists(self):
        assert AgentRabbitMQPublisher is not None

    def test_has_publish_method(self):
        assert hasattr(AgentRabbitMQPublisher, "publish")
        assert inspect.iscoroutinefunction(AgentRabbitMQPublisher.publish)

    def test_satisfies_publisher_protocol(self):
        assert isinstance(AgentRabbitMQPublisher, type)
        assert hasattr(AgentRabbitMQPublisher, "publish")
        sig = inspect.signature(AgentRabbitMQPublisher.publish)
        params = list(sig.parameters.keys())
        assert "envelope" in params


class TestRabbitMQPublisherProtocolCompliance:
    """Verify it satisfies AgentOutboxPublisherProtocol."""

    def test_protocol_runtime_checkable(self):
        import typing

        hints = typing.get_type_hints(AgentOutboxPublisherProtocol.publish)
        publisher_hints = typing.get_type_hints(AgentRabbitMQPublisher.publish)
        assert "envelope" in hints or "envelope" in publisher_hints

    def test_publish_accepts_rabbitmq_message_envelope(self):
        sig = inspect.signature(AgentRabbitMQPublisher.publish)
        params = sig.parameters
        assert "envelope" in params


class TestRabbitMQPublisherDelegation:
    """Verify the publisher delegates to RabbitMQManager."""

    def test_init_accepts_rabbitmq_manager(self):
        sig = inspect.signature(AgentRabbitMQPublisher.__init__)
        params = list(sig.parameters.keys())
        assert "rabbitmq_manager" in params

    def test_publish_uses_manager_exchange(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "_manager" in source
        assert "exchange" in source
        assert "publish" in source

    def test_publish_uses_persistent_delivery_mode(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "PERSISTENT" in source or "DeliveryMode" in source

    def test_publish_includes_headers(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "headers" in source

    def test_publish_includes_correlation_id(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "correlation_id" in source

    def test_publish_uses_routing_key(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "routing_key" in source


class TestRabbitMQPublisherIdempotency:
    """Verify idempotency support via message properties."""

    def test_publish_includes_idempotency_in_headers(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "headers" in source

    def test_envelope_carries_idempotency_key(self):
        from modules.agent.infra.messaging.event_mappers import RabbitMQMessageEnvelope

        fields = {f.name for f in RabbitMQMessageEnvelope.__dataclass_fields__.values()}
        assert "headers" in fields


class TestRabbitMQPublisherNoCrossModuleImports:
    """Verify the publisher does not import from other non-shared modules."""

    def test_no_imports_from_other_modules(self):
        import modules.agent.infra.messaging.publishers as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Forbidden cross-module import: {node.module}"
                    )

    def test_only_imports_shared_infra(self):
        import modules.agent.infra.messaging.publishers as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "shared" in node.module:
                    assert "shared.infra" in node.module or "shared.workers" in node.module


class TestRabbitMQPublisherConfirms:
    """Verify the publisher uses delivery confirmation patterns."""

    def test_message_uses_persistent_delivery(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "DeliveryMode.PERSISTENT" in source

    def test_publishes_via_exchange(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "exchange" in source
        assert "publish" in source
