"""Tests for spec 106 — standardize rabbitmq topology."""
from __future__ import annotations

import pytest

from shared.messaging.dead_letter_policy import DLQ_SUFFIX

from shared.messaging.rabbitmq_topology import (
    EXCHANGE_AUTO_DELETE,
    EXCHANGE_DURABLE,
    EXCHANGE_NAME,
    EXCHANGE_TYPE,
    QUEUE_GROUP_SUFFIX,
    ROUTING_KEY_PATTERN,
    TopologyConfig,
    TopologyValidationError,
    PublisherConfirmsProtocol,
    compute_dlq_name_for_queue,
    compute_queue_name,
    extract_producer_from_routing_key,
    extract_version_from_routing_key,
    validate_binding,
    validate_binding_set,
    validate_exchange_declaration,
    validate_queue_name,
    validate_routing_key,
    validate_topology_config,
)


class TestExchangeDeclaration:
    """Exchange: domain.events, topic, durable."""

    def test_exchange_constants(self):
        assert EXCHANGE_NAME == "domain.events"
        assert EXCHANGE_TYPE == "topic"
        assert EXCHANGE_DURABLE is True
        assert EXCHANGE_AUTO_DELETE is False

    def test_valid_exchange_declaration_passes(self):
        validate_exchange_declaration(
            exchange_name="domain.events",
            exchange_type="topic",
            durable=True,
        )

    def test_wrong_exchange_name_raises(self):
        with pytest.raises(TopologyValidationError, match="exchange_name"):
            validate_exchange_declaration(
                exchange_name="other.events",
                exchange_type="topic",
                durable=True,
            )

    def test_wrong_exchange_type_raises(self):
        with pytest.raises(TopologyValidationError, match="exchange_type"):
            validate_exchange_declaration(
                exchange_name="domain.events",
                exchange_type="fanout",
                durable=True,
            )

    def test_non_durable_exchange_raises(self):
        with pytest.raises(TopologyValidationError, match="durable"):
            validate_exchange_declaration(
                exchange_name="domain.events",
                exchange_type="topic",
                durable=False,
            )


class TestQueueNaming:
    """Queue naming: <consumer_module>.<producer_module>-events."""

    def test_queue_name_convention(self):
        assert compute_queue_name("agent", "identity") == "agent.identity-events"
        assert compute_queue_name("billing", "agent") == "billing.agent-events"
        assert compute_queue_name("metering", "agent") == "metering.agent-events"
        assert compute_queue_name("observability", "agent") == "observability.agent-events"

    def test_valid_queue_name_passes(self):
        validate_queue_name("agent.identity-events")
        validate_queue_name("billing.agent-events")
        validate_queue_name("metering.agent-events")
        validate_queue_name("observability.agent-events")

    def test_invalid_queue_name_raises(self):
        invalid = [
            "agent.identity",
            "agent",
            "Agent.identity-events",
            ".agent.identity-events",
            "agent..identity-events",
            "agent-identity-events",
            "agent.identity.events",
        ]
        for name in invalid:
            with pytest.raises(TopologyValidationError):
                validate_queue_name(name)

    def test_empty_queue_name_raises(self):
        with pytest.raises(TopologyValidationError):
            validate_queue_name("")

    def test_empty_consumer_module_raises(self):
        with pytest.raises(TopologyValidationError, match="consumer_module"):
            compute_queue_name("", "agent")

    def test_empty_producer_module_raises(self):
        with pytest.raises(TopologyValidationError, match="producer_module"):
            compute_queue_name("agent", "")

    def test_invalid_consumer_module_pattern_raises(self):
        with pytest.raises(TopologyValidationError, match="consumer_module"):
            compute_queue_name("InvalidModule", "agent")

    def test_invalid_producer_module_pattern_raises(self):
        with pytest.raises(TopologyValidationError, match="producer_module"):
            compute_queue_name("agent", "InvalidModule")


class TestRoutingKeyValidation:
    """Routing key: <producer_module>.<domain_event>.v<version>."""

    def test_valid_routing_keys_pass(self):
        valid = [
            "agent.execution.completed.v1",
            "agent.execution.failed.v1",
            "identity.user.created.v1",
            "identity.workspace.created.v1",
            "billing.usage.recorded.v2",
            "metering.token.consumed.v1",
        ]
        for rk in valid:
            validate_routing_key(rk)

    def test_invalid_routing_key_format_raises(self):
        invalid = [
            "Agent.execution.v1",
            "agent.execution",
            "agent.v1",
            "agent.execution.v1.extra",
            "agent.execution.v0",
            ".agent.execution.v1",
            "agent..execution.v1",
        ]
        for rk in invalid:
            with pytest.raises(TopologyValidationError):
                validate_routing_key(rk)

    def test_empty_routing_key_raises(self):
        with pytest.raises(TopologyValidationError):
            validate_routing_key("")

    def test_routing_key_pattern_matches_valid(self):
        valid = [
            "agent.execution.completed.v1",
            "identity.user.created.v1",
            "billing.usage.recorded.v2",
        ]
        for rk in valid:
            assert ROUTING_KEY_PATTERN.match(rk), f"Should match: {rk}"

    def test_routing_key_pattern_rejects_invalid(self):
        invalid = [
            "agent",
            "agent.execution",
            "agent.execution.completed",
            "Agent.execution.completed.v1",
            "agent.Execution.completed.v1",
            ".agent.execution.completed.v1",
        ]
        for rk in invalid:
            assert not ROUTING_KEY_PATTERN.match(rk), f"Should not match: {rk}"


class TestBindingValidation:
    """Binding validates routing_key and queue_name compatibility."""

    def test_valid_binding_passes(self):
        validate_binding("agent.execution.completed.v1", "billing.agent-events")
        validate_binding("agent.execution.failed.v1", "metering.agent-events")
        validate_binding("identity.user.created.v1", "agent.identity-events")

    def test_producer_mismatch_raises(self):
        with pytest.raises(TopologyValidationError, match="routing_key producer"):
            validate_binding("agent.execution.completed.v1", "billing.identity-events")

    def test_invalid_routing_key_in_binding_raises(self):
        with pytest.raises(TopologyValidationError):
            validate_binding("bad-key", "billing.agent-events")

    def test_invalid_queue_name_in_binding_raises(self):
        with pytest.raises(TopologyValidationError):
            validate_binding("agent.execution.completed.v1", "bad-queue")

    def test_valid_binding_set_passes(self):
        validate_binding_set(
            routing_keys=["agent.execution.completed.v1", "agent.execution.failed.v1"],
            queue_name="billing.agent-events",
        )

    def test_binding_set_with_mismatch_fails(self):
        with pytest.raises(TopologyValidationError, match="routing_key producer"):
            validate_binding_set(
                routing_keys=["agent.execution.completed.v1", "identity.user.created.v1"],
                queue_name="billing.agent-events",
            )


class TestTopologyConfig:
    """TopologyConfig aggregates exchange, queue, bindings."""

    def test_valid_topology_config_passes(self):
        config = TopologyConfig(
            consumer_module="billing",
            producer_module="agent",
            routing_keys=["agent.execution.completed.v1", "agent.execution.failed.v1"],
        )
        validate_topology_config(config)

    def test_topology_config_queue_name(self):
        config = TopologyConfig(
            consumer_module="billing",
            producer_module="agent",
            routing_keys=["agent.execution.completed.v1"],
        )
        assert config.queue_name == "billing.agent-events"

    def test_topology_config_dlq_name(self):
        config = TopologyConfig(
            consumer_module="billing",
            producer_module="agent",
            routing_keys=["agent.execution.completed.v1"],
        )
        assert config.dlq_name == "billing.agent-events.dlq"

    def test_missing_consumer_module_raises(self):
        config = TopologyConfig(
            consumer_module="",
            producer_module="agent",
            routing_keys=["agent.execution.completed.v1"],
        )
        with pytest.raises(TopologyValidationError, match="consumer_module"):
            validate_topology_config(config)

    def test_missing_producer_module_raises(self):
        config = TopologyConfig(
            consumer_module="billing",
            producer_module="",
            routing_keys=["agent.execution.completed.v1"],
        )
        with pytest.raises(TopologyValidationError, match="producer_module"):
            validate_topology_config(config)

    def test_empty_routing_keys_raises(self):
        config = TopologyConfig(
            consumer_module="billing",
            producer_module="agent",
            routing_keys=[],
        )
        with pytest.raises(TopologyValidationError, match="routing_key"):
            validate_topology_config(config)

    def test_wrong_exchange_in_config_raises(self):
        config = TopologyConfig(
            exchange_name="wrong.events",
            consumer_module="billing",
            producer_module="agent",
            routing_keys=["agent.execution.completed.v1"],
        )
        with pytest.raises(TopologyValidationError, match="exchange_name"):
            validate_topology_config(config)

    def test_default_values(self):
        config = TopologyConfig()
        assert config.exchange_name == "domain.events"
        assert config.exchange_type == "topic"
        assert config.exchange_durable is True
        assert config.routing_keys == []


class TestDLQIntegration:
    """DLQ integration with topology."""

    def test_queue_dlq_name(self):
        assert compute_dlq_name_for_queue("billing.agent-events") == "billing.agent-events.dlq"
        assert compute_dlq_name_for_queue("agent.identity-events") == "agent.identity-events.dlq"

    def test_dlq_suffix_constant(self):
        assert DLQ_SUFFIX == ".dlq"
        assert QUEUE_GROUP_SUFFIX == "events"

    def test_dlq_is_not_a_valid_queue_name(self):
        with pytest.raises(TopologyValidationError):
            validate_queue_name("billing.agent-events.dlq")


class TestPublisherConfirmsProtocol:
    """Publisher confirms are mandatory (runtime_checkable Protocol)."""

    def test_protocol_is_runtime_checkable(self):
        assert issubclass(PublisherConfirmsProtocol, object)

    def test_conforming_publisher_passes_isinstance(self):
        class GoodPublisher:
            def publish(self, exchange: str, routing_key: str, body: bytes) -> bool:
                return True

        pub = GoodPublisher()
        assert isinstance(pub, PublisherConfirmsProtocol)

    def test_non_conforming_publisher_fails_isinstance(self):
        class BadPublisher:
            def send(self, exchange: str, routing_key: str, body: bytes) -> bool:
                return True

        pub = BadPublisher()
        assert not isinstance(pub, PublisherConfirmsProtocol)


class TestRoutingKeyExtraction:
    """Utility functions for routing key parsing."""

    def test_extract_producer(self):
        assert extract_producer_from_routing_key("agent.execution.completed.v1") == "agent"
        assert extract_producer_from_routing_key("identity.user.created.v1") == "identity"
        assert extract_producer_from_routing_key("billing.usage.recorded.v2") == "billing"

    def test_extract_version(self):
        assert extract_version_from_routing_key("agent.execution.completed.v1") == 1
        assert extract_version_from_routing_key("billing.usage.recorded.v2") == 2
        assert extract_version_from_routing_key("identity.workspace.created.v3") == 3

    def test_extract_version_invalid_string(self):
        with pytest.raises(TopologyValidationError, match="version"):
            extract_version_from_routing_key("agent.execution.completed.vx")

    def test_extract_version_no_v_prefix(self):
        with pytest.raises(TopologyValidationError, match="version"):
            extract_version_from_routing_key("agent.execution.completed.1")
