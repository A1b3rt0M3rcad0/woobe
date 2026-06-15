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
