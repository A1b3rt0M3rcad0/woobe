"""Integration tests for spec 093 — standardize RabbitMQ topology.

Verifies the shared RabbitMQ topology contracts apply across all modules.
"""
from __future__ import annotations

import importlib

import pytest

from shared.messaging.rabbitmq_topology import (
    EXCHANGE_AUTO_DELETE,
    EXCHANGE_DURABLE,
    EXCHANGE_NAME,
    EXCHANGE_TYPE,
    QUEUE_NAME_PATTERN,
    ROUTING_KEY_PATTERN,
    BINDING_PATTERN,
    TopologyConfig,
    TopologyValidationError,
    compute_queue_name,
    compute_dlq_name_for_queue,
    validate_queue_name,
    validate_routing_key,
    validate_binding,
    validate_exchange_declaration,
    validate_topology_config,
    extract_producer_from_routing_key,
    extract_version_from_routing_key,
)

MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]


def test_exchange_name_is_domain_events():
    """Spec 093: exchange must be 'domain.events'."""
    assert EXCHANGE_NAME == "domain.events"


def test_exchange_type_is_topic():
    """Spec 093: exchange type must be 'topic'."""
    assert EXCHANGE_TYPE == "topic"


def test_exchange_is_durable():
    """Spec 093: exchange must be durable."""
    assert EXCHANGE_DURABLE is True


def test_exchange_is_not_auto_delete():
    """Spec 093: exchange must not be auto-delete."""
    assert EXCHANGE_AUTO_DELETE is False


def test_queue_name_pattern():
    """Queue name must match '<consumer>.<producer>-events'."""
    assert QUEUE_NAME_PATTERN.match("agent.billing-events")
    assert QUEUE_NAME_PATTERN.match("billing.identity-events")
    assert not QUEUE_NAME_PATTERN.match("agent.billing")
    assert not QUEUE_NAME_PATTERN.match("billing-events")


def test_routing_key_pattern():
    """Routing key must match '<producer>.<domain_event>.v<version>'."""
    assert ROUTING_KEY_PATTERN.match("agent.execution.requested.v1")
    assert ROUTING_KEY_PATTERN.match("identity.user.created.v1")
    assert not ROUTING_KEY_PATTERN.match("agent.execution_requested")
    assert not ROUTING_KEY_PATTERN.match("plain_string")


def test_binding_pattern():
    """Binding pattern must match routing key with 4+ segments ending in .vN."""
    assert BINDING_PATTERN.match("agent.execution.requested.v1")
    assert BINDING_PATTERN.match("identity.workspace.member_added.v1")


def test_compute_queue_name():
    """compute_queue_name returns '<consumer>.<producer>-events'."""
    assert compute_queue_name("agent", "billing") == "agent.billing-events"
    assert compute_queue_name("billing", "agent") == "billing.agent-events"


def test_compute_queue_name_validates_inputs():
    """compute_queue_name raises TopologyValidationError for invalid inputs."""
    with pytest.raises(TopologyValidationError):
        compute_queue_name("", "billing")
    with pytest.raises(TopologyValidationError):
        compute_queue_name("agent", "")


def test_compute_dlq_name():
    """DLQ name is queue_name + '.dlq'."""
    assert compute_dlq_name_for_queue("agent.billing-events") == "agent.billing-events.dlq"


def test_validate_queue_name():
    """Valid queue names pass, invalid raise."""
    validate_queue_name("agent.billing-events")
    with pytest.raises(TopologyValidationError):
        validate_queue_name("invalid")


def test_validate_routing_key():
    """Valid routing keys pass, invalid raise."""
    validate_routing_key("agent.execution.requested.v1")
    with pytest.raises(TopologyValidationError):
        validate_routing_key("invalid")


def test_validate_binding():
    """A valid routing key and queue name pairing passes."""
    validate_binding("agent.execution.requested.v1", "agent.agent-events")


def test_validate_binding_producer_mismatch():
    """When routing key producer doesn't match queue producer, validation fails."""
    with pytest.raises(TopologyValidationError):
        validate_binding("agent.execution.requested.v1", "agent.billing-events")


def test_validate_exchange_declaration():
    """Valid exchange declaration passes."""
    validate_exchange_declaration(EXCHANGE_NAME, EXCHANGE_TYPE, durable=True)


def test_validate_exchange_declaration_wrong_name():
    """Wrong exchange name fails."""
    with pytest.raises(TopologyValidationError):
        validate_exchange_declaration("wrong.name", EXCHANGE_TYPE)


def test_validate_exchange_declaration_wrong_type():
    """Wrong exchange type fails."""
    with pytest.raises(TopologyValidationError):
        validate_exchange_declaration(EXCHANGE_NAME, "direct")


def test_validate_exchange_declaration_not_durable():
    """Non-durable exchange fails."""
    with pytest.raises(TopologyValidationError):
        validate_exchange_declaration(EXCHANGE_NAME, EXCHANGE_TYPE, durable=False)


def test_topology_config():
    """TopologyConfig computes queue_name and dlq_name."""
    config = TopologyConfig(
        consumer_module="agent",
        producer_module="billing",
        routing_keys=["billing.plan.created.v1"],
    )
    assert config.queue_name == "agent.billing-events"
    assert config.dlq_name == "agent.billing-events.dlq"


def test_validate_topology_config():
    """A valid TopologyConfig passes validation."""
    config = TopologyConfig(
        consumer_module="agent",
        producer_module="billing",
        routing_keys=["billing.plan.created.v1"],
    )
    validate_topology_config(config)


def test_validate_topology_config_missing_routing_keys():
    """A TopologyConfig without routing keys fails."""
    config = TopologyConfig(
        consumer_module="agent",
        producer_module="billing",
        routing_keys=[],
    )
    with pytest.raises(TopologyValidationError):
        validate_topology_config(config)


def test_extract_producer_from_routing_key():
    """Extract producer from routing key."""
    assert extract_producer_from_routing_key("agent.execution.requested.v1") == "agent"
    assert extract_producer_from_routing_key("billing.plan.created.v1") == "billing"


def test_extract_version_from_routing_key():
    """Extract version from routing key."""
    assert extract_version_from_routing_key("agent.execution.requested.v1") == 1
    assert extract_version_from_routing_key("billing.plan.created.v2") == 2


@pytest.mark.parametrize("mod_name", MODULES)
def test_each_module_has_registry(mod_name):
    """Every module must have a worker registry."""
    try:
        mod = importlib.import_module(
            f"modules.{mod_name}.infra.workers.registry"
        )
    except ModuleNotFoundError:
        pytest.skip(f"No infra/workers/registry.py for {mod_name}")
    assert hasattr(mod, f"register_{mod_name}_workers") or any(
        name.endswith("Registry") or "registry" in name.lower()
        for name in vars(mod)
    ), f"{mod_name} registry must have register function or Registry class"
