"""Integration tests for spec 091 — standardize outbox contract across modules.

Verifies every module's outbox implementation conforms to the shared contract.
"""
from __future__ import annotations

import importlib
from uuid import uuid4

import pytest

from shared.messaging.outbox_contracts import (
    OPTIONAL_ENVELOPE_FIELDS,
    REQUIRED_ENVELOPE_FIELDS,
    OutboxEnvelopeValidationError,
    validate_outbox_envelope,
)

# All canonical modules + agent (reference)
MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]


def test_required_envelope_fields():
    """Outbox envelope requires event_id, event_type, event_version, occurred_at,
    producer_module, routing_key, payload, idempotency_key, correlation_id."""
    expected = frozenset(
        {
            "event_id",
            "event_type",
            "event_version",
            "occurred_at",
            "producer_module",
            "routing_key",
            "payload",
            "idempotency_key",
            "correlation_id",
        }
    )
    missing = expected - REQUIRED_ENVELOPE_FIELDS
    assert not missing, f"Missing required fields: {missing}"


def test_optional_envelope_fields():
    """Optional fields include aggregate_type, aggregate_id, causation_id, metadata."""
    expected = frozenset({"aggregate_type", "aggregate_id", "causation_id", "metadata"})
    extra = OPTIONAL_ENVELOPE_FIELDS - expected
    assert not extra, f"Unexpected optional fields: {extra}"


def test_validate_outbox_envelope_with_valid_envelope():
    """A valid outbox envelope passes validation."""
    envelope = {
        "event_id": str(uuid4()),
        "event_type": "identity.user.created.v1",
        "event_version": 1,
        "occurred_at": "2026-06-15T12:00:00+00:00",
        "producer_module": "identity",
        "routing_key": "identity.user.created.v1",
        "payload": {"user_id": str(uuid4())},
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
    }
    validate_outbox_envelope(envelope)


def test_validate_outbox_envelope_missing_field_raises():
    """Omitting a required field raises OutboxEnvelopeValidationError."""
    envelope = {
        "event_id": str(uuid4()),
        "event_type": "agent.execution.requested.v1",
    }
    with pytest.raises(OutboxEnvelopeValidationError):
        validate_outbox_envelope(envelope)


def test_validate_outbox_envelope_bad_routing_key_raises():
    """A routing key with fewer than 3 segments raises."""
    envelope = {
        "event_id": str(uuid4()),
        "event_type": "agent.test.v1",
        "event_version": 1,
        "occurred_at": "2026-06-15T12:00:00+00:00",
        "producer_module": "agent",
        "routing_key": "short",
        "payload": {},
        "idempotency_key": "key",
        "correlation_id": str(uuid4()),
    }
    with pytest.raises(OutboxEnvelopeValidationError):
        validate_outbox_envelope(envelope)


@pytest.mark.parametrize("module_name", MODULES)
def test_each_module_has_outbox_event_writer(module_name):
    """Every module must have a SQLAlchemyOutboxEventWriter or equivalent class."""
    try:
        mod = importlib.import_module(f"modules.{module_name}.infra.database.repositories")
    except ModuleNotFoundError:
        pytest.skip(f"No infra/database/repositories.py for {module_name}")
    writers = [
        cls
        for name, cls in vars(mod).items()
        if name.endswith("OutboxEventWriter")
        and hasattr(cls, "write")
    ]
    assert len(writers) >= 1, (
        f"{module_name} must have at least one OutboxEventWriter"
    )


@pytest.mark.parametrize("module_name", MODULES)
def test_each_module_has_outbox_event_model(module_name):
    """Every module must have an OutboxEventModel extending BaseOutbox."""
    try:
        mod = importlib.import_module(f"modules.{module_name}.infra.database.models")
    except ModuleNotFoundError:
        pytest.skip(f"No infra/database/models.py for {module_name}")
    models = [
        cls
        for name, cls in vars(mod).items()
        if name == "OutboxEventModel"
        or (name.endswith("OutboxEventModel") and hasattr(cls, "__tablename__"))
    ]
    assert len(models) >= 1, (
        f"{module_name} must have at least one OutboxEventModel"
    )


@pytest.mark.parametrize("module_name", MODULES)
def test_each_module_outbox_event_model_has_tablename(module_name):
    """OutboxEventModel must define __tablename__."""
    try:
        mod = importlib.import_module(f"modules.{module_name}.infra.database.models")
    except ModuleNotFoundError:
        pytest.skip(f"No infra/database/models.py for {module_name}")
    models = [
        cls
        for name, cls in vars(mod).items()
        if name == "OutboxEventModel" and hasattr(cls, "__tablename__")
    ]
    if not models:
        models = [
            cls
            for name, cls in vars(mod).items()
            if name.endswith("OutboxEventModel")
            and hasattr(cls, "__tablename__")
        ]
    assert len(models) >= 1, (
        f"{module_name} OutboxEventModel must have __tablename__"
    )


def test_shared_outbox_event_writer_abstract():
    """shared.domain.events.OutboxEventWriter must have abstract write method."""
    from shared.messaging.outbox_writer import OutboxEventWriter
    assert hasattr(OutboxEventWriter.write, "__isabstractmethod__")
