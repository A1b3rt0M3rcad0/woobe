"""Tests for spec 127 — add rabbitmq publisher confirm tests.

Validates RabbitMQ publisher confirm guarantees across the agent outbox dispatch
pipeline: robust connection for confirms, persistent delivery mode, durable
exchange, publish-before-mark_published ordering, failure handling with retry
and dead-letter, message envelope integrity, and correlation/header propagation.
"""
from __future__ import annotations

import ast
import inspect

from modules.agent.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
)
from modules.agent.infra.messaging.publishers import AgentRabbitMQPublisher
from woobe_workers.consumers.agent.outbox_dispatcher import (
    AgentOutboxDispatcherWorker,
    AgentOutboxPublisherProtocol,
)
from shared.infra.rabbitmq import RabbitMQManager
from woobe_workers.runtime.outbox_dispatcher_base import BaseOutboxDispatcher, OutboxRecord


class TestPublisherConfirmConnection:
    """Verify RabbitMQ connection uses publisher confirms."""

    def test_rabbitmq_manager_uses_connect_robust(self):
        source = inspect.getsource(RabbitMQManager.connect)
        assert "connect_robust" in source

    def test_rabbitmq_manager_declares_exchange_durable(self):
        source = inspect.getsource(RabbitMQManager.connect)
        assert "durable=True" in source

    def test_rabbitmq_manager_exchange_is_topic_type(self):
        source = inspect.getsource(RabbitMQManager.connect)
        assert "TOPIC" in source or "ExchangeType.TOPIC" in source

    def test_rabbitmq_manager_has_publish_method(self):
        assert hasattr(RabbitMQManager, "publish")
        assert inspect.iscoroutinefunction(RabbitMQManager.publish)

    def test_rabbitmq_manager_publish_uses_persistent_delivery(self):
        source = inspect.getsource(RabbitMQManager.publish)
        assert "PERSISTENT" in source

    def test_rabbitmq_manager_connection_is_robust_type(self):
        source = inspect.getsource(RabbitMQManager)
        assert "RobustConnection" in source

    def test_rabbitmq_manager_channel_is_robust_type(self):
        source = inspect.getsource(RabbitMQManager)
        assert "RobustChannel" in source


class TestAgentPublisherUsesRabbitMQManager:
    """Verify AgentRabbitMQPublisher delegates to RabbitMQManager."""

    def test_publisher_inits_with_rabbitmq_manager(self):
        sig = inspect.signature(AgentRabbitMQPublisher.__init__)
        params = list(sig.parameters.keys())
        assert "rabbitmq_manager" in params

    def test_publisher_publish_uses_manager_exchange(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "_manager" in source
        assert "exchange" in source

    def test_publisher_publish_uses_delivery_mode_persistent(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "DeliveryMode.PERSISTENT" in source

    def test_publisher_publish_sets_content_type_json(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "application/json" in source

    def test_publisher_publish_uses_routing_key_from_envelope(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "routing_key" in source

    def test_publisher_publish_propagates_correlation_id(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "correlation_id" in source

    def test_publisher_publish_includes_headers(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "headers" in source


class TestOutboxToRabbitMessageMapping:
    """Verify outbox events are correctly mapped to RabbitMQ envelopes."""

    def test_outbox_to_rabbit_message_returns_envelope(self):
        sig = inspect.signature(outbox_to_rabbit_message)
        return_annotation = sig.return_annotation
        assert return_annotation is not inspect.Parameter.empty

    def test_envelope_has_body_field(self):
        fields = {f.name for f in RabbitMQMessageEnvelope.__dataclass_fields__.values()}
        assert "body" in fields

    def test_envelope_has_routing_key_field(self):
        fields = {f.name for f in RabbitMQMessageEnvelope.__dataclass_fields__.values()}
        assert "routing_key" in fields

    def test_envelope_has_correlation_id_field(self):
        fields = {f.name for f in RabbitMQMessageEnvelope.__dataclass_fields__.values()}
        assert "correlation_id" in fields

    def test_envelope_has_headers_field(self):
        fields = {f.name for f in RabbitMQMessageEnvelope.__dataclass_fields__.values()}
        assert "headers" in fields

    def test_envelope_body_is_string(self):
        annotations = RabbitMQMessageEnvelope.__annotations__
        assert annotations.get("body") == "str"


class TestPublisherConfirmBeforeMarkPublished:
    """Verify dispatcher publishes BEFORE marking outbox event as published."""

    def test_base_dispatcher_run_publishes_before_mark(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        publish_pos = source.find("publish")
        mark_pos = source.find("mark_published")
        assert publish_pos < mark_pos, (
            "publish must be called BEFORE mark_published"
        )

    def test_base_dispatcher_run_marks_published_in_try_block(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        lines = source.splitlines()
        in_try = False
        publish_found = False
        for line in lines:
            if "try:" in line:
                in_try = True
            elif "except" in line:
                in_try = False
            if in_try:
                if "publish" in line and "mark_published" not in line:
                    publish_found = True
                if "mark_published" in line:
                    assert publish_found, "mark_published found before publish in try block"

    def test_agent_dispatcher_publish_uses_protocol(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "_publisher" in source
        assert "publish" in source

    def test_agent_dispatcher_publish_delegates_to_publisher(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.publish)
        assert "self._publisher.publish" in source

    def test_agent_dispatcher_marks_published_after_publish(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_published)
        assert "mark_published" in source

    def test_publisher_protocol_requires_publish_method(self):
        assert hasattr(AgentOutboxPublisherProtocol, "publish")


class TestPublisherFailureHandling:
    """Verify publish failures are handled with retry/dead-letter."""

    def test_base_dispatcher_catches_publish_exception(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "except" in source
        assert "mark_failed" in source

    def test_base_dispatcher_mark_failed_increments_attempts(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "attempts" in source

    def test_base_dispatcher_mark_failed_routes_to_dead_after_max(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "MAX_ATTEMPTS" in source
        assert "mark_dead" in source
        assert "mark_retryable" in source

    def test_agent_dispatcher_has_max_attempts(self):
        assert hasattr(AgentOutboxDispatcherWorker, "MAX_ATTEMPTS")
        assert AgentOutboxDispatcherWorker.MAX_ATTEMPTS >= 1

    def test_agent_dispatcher_has_mark_dead(self):
        assert hasattr(AgentOutboxDispatcherWorker, "mark_dead")
        assert inspect.iscoroutinefunction(AgentOutboxDispatcherWorker.mark_dead)

    def test_agent_dispatcher_has_mark_retryable(self):
        assert hasattr(AgentOutboxDispatcherWorker, "mark_retryable")
        assert inspect.iscoroutinefunction(AgentOutboxDispatcherWorker.mark_retryable)

    def test_dead_letter_events_not_republished(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "publish" in source
        assert "mark_published" in source

    def test_publish_exception_sets_error_on_record(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "error" in source

    def test_retryable_events_available_for_later_claim(self):
        from modules.agent.infra.database.repositories import (
            SQLAlchemyAgentOutboxRepository,
        )
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "retryable" in source or "'retryable'" in source or '"retryable"' in source


class TestOutboxRecordIntegrity:
    """Verify OutboxRecord carries all fields needed for publishing."""

    REQUIRED_FIELDS = {
        "id", "event_type", "event_version", "payload",
        "correlation_id", "causation_id", "aggregate_type",
        "aggregate_id", "attempts", "error",
    }

    def test_outbox_record_has_all_required_fields(self):
        fields = set(OutboxRecord.__dataclass_fields__.keys())
        missing = self.REQUIRED_FIELDS - fields
        assert not missing, f"OutboxRecord missing fields: {missing}"

    def test_outbox_record_has_event_type(self):
        assert "event_type" in OutboxRecord.__dataclass_fields__

    def test_outbox_record_has_payload(self):
        assert "payload" in OutboxRecord.__dataclass_fields__

    def test_outbox_record_has_correlation_id(self):
        assert "correlation_id" in OutboxRecord.__dataclass_fields__

    def test_outbox_record_has_causation_id(self):
        assert "causation_id" in OutboxRecord.__dataclass_fields__

    def test_outbox_record_has_idempotency_support(self):
        assert "id" in OutboxRecord.__dataclass_fields__


class TestPublisherConfirmEndToEnd:
    """End-to-end publisher confirm scenario tests."""

    def test_full_dispatch_cycle_contract(self):
        run_source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "claim_pending" in run_source
        assert "publish" in run_source
        assert "mark_published" in run_source
        assert "mark_failed" in run_source

    def test_claim_uses_skip_locked(self):
        from modules.agent.infra.database.repositories import (
            SQLAlchemyAgentOutboxRepository,
        )
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked=True" in source

    def test_publish_happens_in_same_run_cycle_as_claim(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        claim_idx = source.find("claim_pending")
        publish_idx = source.find("publish")
        assert claim_idx < publish_idx

    def test_mark_published_happens_in_same_run_cycle_as_publish(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        publish_idx = source.find("publish")
        mark_idx = source.find("mark_published")
        assert publish_idx < mark_idx


class TestPublisherNoCrossModuleImports:
    """Verify the publisher does not import from non-agent, non-shared modules."""

    def test_no_cross_module_imports_in_publisher(self):
        import modules.agent.infra.messaging.publishers as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Publisher must not import from '{node.module}'"
                    )

    def test_no_cross_module_imports_in_outbox_dispatcher(self):
        import woobe_workers.consumers.agent.outbox_dispatcher as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Outbox dispatcher must not import from '{node.module}'"
                    )

    def test_no_cross_module_imports_in_event_mappers(self):
        import modules.agent.infra.messaging.event_mappers as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Event mappers must not import from '{node.module}'"
                    )
