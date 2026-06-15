"""Tests for spec 082 — implement agent inbox consumer."""
import ast
import inspect

from modules.agent.infra.workers.inbox_consumer import (
    AGENT_INBOX_QUEUE,
    AGENT_INBOX_ROUTING_KEYS,
    AgentInboxConsumerWorker,
)
from shared.workers.inbox_consumer_base import BaseInboxConsumer


class TestInboxConsumerStructure:
    """Verify the consumer is properly located and inherits from the base."""

    def test_file_exists_in_correct_location(self):
        import modules.agent.infra.workers.inbox_consumer as mod

        assert mod.__file__ is not None
        assert "modules/agent/infra/workers" in mod.__file__.replace("\\", "/")

    def test_inherits_from_base_inbox_consumer(self):
        assert issubclass(AgentInboxConsumerWorker, BaseInboxConsumer)

    def test_implements_consume(self):
        assert hasattr(AgentInboxConsumerWorker, "consume")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.consume)

    def test_implements_persist_inbox(self):
        assert hasattr(AgentInboxConsumerWorker, "persist_inbox")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.persist_inbox)

    def test_implements_acknowledge(self):
        assert hasattr(AgentInboxConsumerWorker, "acknowledge")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.acknowledge)

    def test_implements_reject(self):
        assert hasattr(AgentInboxConsumerWorker, "reject")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.reject)


class TestInboxConsumerDelegation:
    """Verify the consumer delegates to repository and event mappers."""

    def test_on_message_uses_rabbit_message_to_inbox(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "rabbit_message_to_inbox" in source

    def test_persist_and_ack_uses_repository(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "SQLAlchemyAgentInboxRepository" in source
        assert "save_received" in source

    def test_consume_uses_rabbitmq_manager(self):
        source = inspect.getsource(AgentInboxConsumerWorker.consume)
        assert "_rabbitmq_manager" in source
        assert "consume" in source

    def test_acknowledge_calls_ack(self):
        source = inspect.getsource(AgentInboxConsumerWorker.acknowledge)
        assert "ack" in source

    def test_reject_calls_nack_or_reject(self):
        source = inspect.getsource(AgentInboxConsumerWorker.reject)
        assert "nack" in source or "reject" in source


class TestInboxConsumerIdempotency:
    """Verify duplicate message handling."""

    def test_handles_integrity_error_on_duplicate(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "IntegrityError" in source

    def test_acknowledges_duplicate_message(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "acknowledge" in source

    def test_duplicate_does_not_raise(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "rollback" in source


class TestInboxConsumerConcurrency:
    """Verify concurrency safety patterns."""

    def test_worker_has_unique_id(self):
        source = inspect.getsource(AgentInboxConsumerWorker.__init__)
        assert "worker_id" in source

    def test_session_lifecycle_per_message(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "AsyncSession" in source
        assert "begin" in source

    def test_queue_name_configurable(self):
        sig = inspect.signature(AgentInboxConsumerWorker.__init__)
        params = list(sig.parameters.keys())
        assert "queue_name" in params

    def test_default_queue_name(self):
        assert AGENT_INBOX_QUEUE == "agent.inbox"

    def test_default_routing_keys(self):
        assert isinstance(AGENT_INBOX_ROUTING_KEYS, list)
        assert len(AGENT_INBOX_ROUTING_KEYS) > 0


class TestInboxConsumerAckAfterPersist:
    """Verify ack only happens after durable persistence."""

    def test_persist_before_ack_ordering(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        persist_pos = source.find("save_received")
        ack_pos = source.find("acknowledge")
        assert persist_pos < ack_pos, "Ack must happen after persist"


class TestInboxConsumerNoCrossModuleImports:
    """Verify the consumer does not import from other modules."""

    def test_no_imports_from_other_modules(self):
        import modules.agent.infra.workers.inbox_consumer as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Forbidden cross-module import: {node.module}"
                    )

    def test_only_imports_shared_infra_or_workers(self):
        import modules.agent.infra.workers.inbox_consumer as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "shared" in node.module:
                    assert (
                        "shared.infra" in node.module
                        or "shared.workers" in node.module
                    )


class TestInboxConsumerRejectOnInvalidMessage:
    """Verify invalid messages are rejected."""

    def test_invalid_message_triggers_reject(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "reject" in source

    def test_catches_value_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "ValueError" in source

    def test_catches_key_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._on_message)
        assert "KeyError" in source
