"""Architecture tests for cross-cutting messaging contracts (specs 090-094).

Each spec in the transversal phase adds validation clauses to this file.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


SHARED_MESSAGING_DIR = Path("src/shared/messaging")


def test_event_envelope_module_exists():
    """Spec 090: shared.messaging.event_envelope must exist."""
    from shared.messaging import event_envelope  # noqa: F811
    assert hasattr(event_envelope, "EventEnvelope")
    assert hasattr(event_envelope, "validate_event_envelope")


def test_event_envelope_has_required_fields():
    """Spec 090: EventEnvelope must define event_id, event_type, event_version,
    occurred_at, producer_module, routing_key, payload, idempotency_key,
    correlation_id as required fields."""
    from shared.messaging.event_envelope import REQUIRED_ENVELOPE_FIELDS
    expected = frozenset({
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer_module",
        "routing_key",
        "payload",
        "idempotency_key",
        "correlation_id",
    })
    assert expected.issubset(REQUIRED_ENVELOPE_FIELDS), (
        f"Expected {expected} to be subset of REQUIRED_ENVELOPE_FIELDS"
    )


def test_event_envelope_has_validation():
    """Spec 090: validate_event_envelope function must be callable."""
    from shared.messaging.event_envelope import validate_event_envelope
    assert callable(validate_event_envelope)


def test_event_envelope_has_causation_id():
    """Spec 090: EventEnvelope dataclass must accept causation_id (optional)."""
    from shared.messaging.event_envelope import EventEnvelope
    fields = {f.name for f in EventEnvelope.__dataclass_fields__.values()}
    assert "causation_id" in fields


def test_event_envelope_has_metadata():
    """Spec 090: EventEnvelope dataclass must accept metadata (optional container)."""
    from shared.messaging.event_envelope import EventEnvelope
    fields = {f.name for f in EventEnvelope.__dataclass_fields__.values()}
    assert "metadata" in fields


def test_event_envelope_has_event_type_pattern():
    """Spec 090: EVENT_TYPE_PATTERN regex must be defined."""
    from shared.messaging.event_envelope import EVENT_TYPE_PATTERN
    assert EVENT_TYPE_PATTERN.match("agent.execution.requested.v1")
    assert not EVENT_TYPE_PATTERN.match("agent.execution_requested")
    assert not EVENT_TYPE_PATTERN.match("plain_string")


def test_event_envelope_has_routing_key_pattern():
    """Spec 090: ROUTING_KEY_PATTERN regex must be defined."""
    from shared.messaging.event_envelope import ROUTING_KEY_PATTERN
    assert ROUTING_KEY_PATTERN.match("agent.execution.requested.v1")


def test_shared_messaging_init_importable():
    """The shared.messaging package must be importable."""
    mod = importlib.import_module("shared.messaging")
    assert mod is not None


def test_shared_messaging_package_has_expected_modules():
    """All shared messaging contract modules must exist."""
    expected = {
        "event_envelope",
        "outbox_contracts",
        "inbox_contracts",
        "rabbitmq_topology",
        "retry_policy",
        "dead_letter_policy",
        "idempotency_contracts",
        "versioning_policy",
        "compatibility_policy",
    }
    found = {p.stem for p in SHARED_MESSAGING_DIR.glob("*.py") if p.stem != "__init__"}
    missing = expected - found
    assert not missing, f"Missing shared messaging modules: {missing}"


# --- Spec 091: Outbox contract ---


def test_outbox_contracts_module_exists():
    """Spec 091: shared.messaging.outbox_contracts must exist."""
    from shared.messaging import outbox_contracts
    assert hasattr(outbox_contracts, "OutboxEventProtocol")
    assert hasattr(outbox_contracts, "validate_outbox_envelope")


def test_outbox_contracts_has_required_envelope_fields():
    """Spec 091: REQUIRED_ENVELOPE_FIELDS must include all mandated fields."""
    from shared.messaging.outbox_contracts import REQUIRED_ENVELOPE_FIELDS
    expected = frozenset({
        "event_id",
        "event_type",
        "event_version",
        "occurred_at",
        "producer_module",
        "routing_key",
        "payload",
        "idempotency_key",
        "correlation_id",
    })
    assert expected.issubset(REQUIRED_ENVELOPE_FIELDS)


def test_outbox_contracts_has_validation_function():
    """Spec 091: validate_outbox_envelope must be callable."""
    from shared.messaging.outbox_contracts import validate_outbox_envelope
    assert callable(validate_outbox_envelope)


def test_outbox_contracts_has_protocol():
    """Spec 091: OutboxEventProtocol must define event_type, routing_key
    and other expected properties."""
    from shared.messaging.outbox_contracts import OutboxEventProtocol
    props = ["event_type", "event_version", "routing_key",
             "idempotency_key", "correlation_id", "payload", "status"]
    for p in props:
        assert hasattr(OutboxEventProtocol, p), (
            f"OutboxEventProtocol missing property: {p}"
        )


def test_shared_domain_events_has_abstract_outbox_writer():
    """Spec 091: shared.domain.events.OutboxEventWriter must exist with abstract write()."""
    from shared.domain.events import OutboxEventWriter
    assert hasattr(OutboxEventWriter.write, "__isabstractmethod__")


def test_each_module_outbox_event_writer_exists():
    """Every canonical module has a SQLAlchemyOutboxEventWriter in infra/database/repositories."""
    modules = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]
    for mod_name in modules:
        try:
            mod = importlib.import_module(
                f"modules.{mod_name}.infra.database.repositories"
            )
        except ModuleNotFoundError:
            pytest.skip(f"No infra/database/repositories for {mod_name}")
        writers = [
            cls for name, cls in vars(mod).items()
            if name.endswith("OutboxEventWriter") and hasattr(cls, "write")
        ]
        assert len(writers) >= 1, (
            f"{mod_name} must have at least one OutboxEventWriter"
        )


# --- Spec 092: Inbox contract ---


def test_inbox_contracts_module_exists():
    """Spec 092: shared.messaging.inbox_contracts must exist."""
    from shared.messaging import inbox_contracts
    assert hasattr(inbox_contracts, "InboxEventProtocol")
    assert hasattr(inbox_contracts, "validate_inbox_envelope")


def test_inbox_contracts_has_required_fields():
    """Spec 092: REQUIRED_INBOX_ENVELOPE_FIELDS must include all mandated fields."""
    from shared.messaging.inbox_contracts import REQUIRED_INBOX_ENVELOPE_FIELDS
    expected = frozenset({
        "event_type",
        "event_version",
        "routing_key",
        "idempotency_key",
        "correlation_id",
        "producer_module",
        "occurred_at",
        "payload",
    })
    assert expected.issubset(REQUIRED_INBOX_ENVELOPE_FIELDS)


def test_inbox_contracts_has_validation_function():
    """Spec 092: validate_inbox_envelope must be callable."""
    from shared.messaging.inbox_contracts import validate_inbox_envelope
    assert callable(validate_inbox_envelope)


def test_inbox_contracts_has_protocol():
    """Spec 092: InboxEventProtocol must define all expected properties."""
    from shared.messaging.inbox_contracts import InboxEventProtocol
    props = ["message_id", "producer_module", "consumer_module",
             "event_type", "event_version", "routing_key",
             "idempotency_key", "correlation_id", "payload", "status"]
    for p in props:
        assert hasattr(InboxEventProtocol, p), (
            f"InboxEventProtocol missing property: {p}"
        )


def test_shared_infra_database_inbox_model_exists():
    """Spec 092: shared.infra.database.inbox.InboxEventModel must exist as abstract."""
    from shared.infra.database.inbox import InboxEventModel
    assert hasattr(InboxEventModel, "__abstract__")


def test_each_module_has_inbox_event_model():
    """Every canonical module has an InboxEventModel in infra/database/models."""
    modules = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]
    for mod_name in modules:
        try:
            mod = importlib.import_module(
                f"modules.{mod_name}.infra.database.models"
            )
        except ModuleNotFoundError:
            pytest.skip(f"No infra/database/models for {mod_name}")
        models = [
            cls for name, cls in vars(mod).items()
            if name == "InboxEventModel" and hasattr(cls, "__tablename__")
        ]
        if not models:
            models = [
                cls for name, cls in vars(mod).items()
                if name.endswith("InboxEventModel") and hasattr(cls, "__tablename__")
            ]
        assert len(models) >= 1, (
            f"{mod_name} must have at least one InboxEventModel"
        )


# --- Spec 093: RabbitMQ topology ---


def test_rabbitmq_topology_module_exists():
    """Spec 093: shared.messaging.rabbitmq_topology must exist."""
    from shared.messaging import rabbitmq_topology
    assert hasattr(rabbitmq_topology, "EXCHANGE_NAME")
    assert hasattr(rabbitmq_topology, "compute_queue_name")
    assert hasattr(rabbitmq_topology, "validate_routing_key")


def test_rabbitmq_topology_exchange_constants():
    """Spec 093: EXCHANGE_NAME, EXCHANGE_TYPE, EXCHANGE_DURABLE must be defined."""
    from shared.messaging.rabbitmq_topology import (
        EXCHANGE_NAME,
        EXCHANGE_TYPE,
        EXCHANGE_DURABLE,
    )
    assert EXCHANGE_NAME == "domain.events"
    assert EXCHANGE_TYPE == "topic"
    assert EXCHANGE_DURABLE is True


def test_rabbitmq_topology_has_validation_functions():
    """Spec 093: validate_queue_name, validate_routing_key, validate_binding
    and validate_exchange_declaration must be callable."""
    from shared.messaging.rabbitmq_topology import (
        validate_queue_name,
        validate_routing_key,
        validate_binding,
        validate_exchange_declaration,
    )
    assert callable(validate_queue_name)
    assert callable(validate_routing_key)
    assert callable(validate_binding)
    assert callable(validate_exchange_declaration)


def test_rabbitmq_topology_has_topology_config():
    """Spec 093: TopologyConfig dataclass must exist."""
    from shared.messaging.rabbitmq_topology import TopologyConfig
    config = TopologyConfig(
        consumer_module="agent",
        producer_module="billing",
        routing_keys=["billing.plan.created.v1"],
    )
    assert config.queue_name == "agent.billing-events"


def test_rabbitmq_topology_has_validate_topology_config():
    """Spec 093: validate_topology_config must be callable."""
    from shared.messaging.rabbitmq_topology import (
        TopologyConfig,
        validate_topology_config,
    )
    config = TopologyConfig(
        consumer_module="agent",
        producer_module="billing",
        routing_keys=["billing.plan.created.v1"],
    )
    validate_topology_config(config)


def test_rabbitmq_topology_has_compute_dlq_name():
    """Spec 093: compute_dlq_name_for_queue must exist."""
    from shared.messaging.rabbitmq_topology import compute_dlq_name_for_queue
    assert callable(compute_dlq_name_for_queue)
    assert compute_dlq_name_for_queue("agent.billing-events") == "agent.billing-events.dlq"


def test_rabbitmq_topology_has_extract_producer():
    """Spec 093: extract_producer_from_routing_key must exist."""
    from shared.messaging.rabbitmq_topology import extract_producer_from_routing_key
    assert extract_producer_from_routing_key("agent.execution.requested.v1") == "agent"


def test_rabbitmq_topology_has_extract_version():
    """Spec 093: extract_version_from_routing_key must exist."""
    from shared.messaging.rabbitmq_topology import extract_version_from_routing_key
    assert extract_version_from_routing_key("agent.execution.requested.v1") == 1
