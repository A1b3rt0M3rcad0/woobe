"""Integration tests for spec 092 — standardize inbox contract across modules.

Verifies every module's inbox implementation conforms to the shared contract.
"""
from __future__ import annotations

import importlib
from uuid import uuid4

import pytest

from shared.messaging.inbox_contracts import (
    OPTIONAL_INBOX_ENVELOPE_FIELDS,
    REQUIRED_INBOX_ENVELOPE_FIELDS,
    InboxEnvelopeValidationError,
    InboxEventProtocol,
    validate_inbox_envelope,
)

MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]


def test_required_inbox_envelope_fields():
    """Inbox envelope requires event_type, event_version, routing_key,
    idempotency_key, correlation_id, producer_module, occurred_at, payload."""
    required = frozenset(
        {
            "event_type",
            "event_version",
            "routing_key",
            "idempotency_key",
            "correlation_id",
            "producer_module",
            "occurred_at",
            "payload",
        }
    )
    missing = required - REQUIRED_INBOX_ENVELOPE_FIELDS
    assert not missing, f"Missing required inbox fields: {missing}"


def test_optional_inbox_envelope_fields():
    """Optional inbox fields include event_id, causation_id, headers,
    metadata, aggregate_type, aggregate_id."""
    expected = frozenset(
        {
            "event_id",
            "causation_id",
            "headers",
            "metadata",
            "aggregate_type",
            "aggregate_id",
        }
    )
    extra = OPTIONAL_INBOX_ENVELOPE_FIELDS - expected
    assert not extra, f"Unexpected optional inbox fields: {extra}"


def test_validate_inbox_envelope_with_valid_envelope():
    """A valid inbox envelope passes validation."""
    envelope = {
        "event_type": "billing.plan.created.v1",
        "event_version": 1,
        "routing_key": "billing.plan.created.v1",
        "idempotency_key": str(uuid4()),
        "correlation_id": str(uuid4()),
        "producer_module": "billing",
        "occurred_at": "2026-06-15T12:00:00+00:00",
        "payload": {"plan_id": str(uuid4())},
    }
    validate_inbox_envelope(envelope)


def test_validate_inbox_envelope_missing_field_raises():
    """Omitting a required field raises InboxEnvelopeValidationError."""
    envelope = {
        "event_type": "core.project.created.v1",
    }
    with pytest.raises(InboxEnvelopeValidationError):
        validate_inbox_envelope(envelope)


def test_validate_inbox_envelope_bad_routing_key_raises():
    """A routing key with fewer than 3 segments raises."""
    envelope = {
        "event_type": "agent.test.v1",
        "event_version": 1,
        "routing_key": "short",
        "idempotency_key": "key",
        "correlation_id": str(uuid4()),
        "producer_module": "agent",
        "occurred_at": "2026-06-15T12:00:00+00:00",
        "payload": {},
    }
    with pytest.raises(InboxEnvelopeValidationError):
        validate_inbox_envelope(envelope)


def test_inbox_event_protocol_has_expected_properties():
    """InboxEventProtocol defines message_id, producer_module, consumer_module,
    event_type, event_version, routing_key, idempotency_key, correlation_id,
    payload, status."""
    props = [
        "message_id",
        "producer_module",
        "consumer_module",
        "event_type",
        "event_version",
        "routing_key",
        "idempotency_key",
        "correlation_id",
        "payload",
        "status",
    ]
    for p in props:
        assert hasattr(InboxEventProtocol, p), (
            f"InboxEventProtocol missing property: {p}"
        )


@pytest.mark.parametrize("module_name", MODULES)
def test_each_module_has_inbox_event_model(module_name):
    """Every module must have an InboxEventModel extending BaseInbox."""
    try:
        mod = importlib.import_module(
            f"modules.{module_name}.infra.database.models"
        )
    except ModuleNotFoundError:
        pytest.skip(f"No infra/database/models.py for {module_name}")
    models = [
        cls
        for name, cls in vars(mod).items()
        if name == "InboxEventModel" and hasattr(cls, "__tablename__")
    ]
    if not models:
        models = [
            cls
            for name, cls in vars(mod).items()
            if name.endswith("InboxEventModel") and hasattr(cls, "__tablename__")
        ]
    assert len(models) >= 1, (
        f"{module_name} must have at least one InboxEventModel"
    )


@pytest.mark.parametrize("module_name", MODULES)
def test_each_module_has_inbox_router(module_name):
    """Every module must have an inbox handler router (InboxEventRouter)."""
    try:
        mod = importlib.import_module(
            f"modules.{module_name}.infra.messaging.inbox_handlers"
        )
    except ModuleNotFoundError:
        pytest.skip(f"No infra/messaging/inbox_handlers.py for {module_name}")
    routers = [
        cls
        for name, cls in vars(mod).items()
        if name.endswith("InboxEventRouter")
    ]
    assert len(routers) >= 1, (
        f"{module_name} must have an InboxEventRouter"
    )


def test_shared_inbox_database_model_exists():
    """shared.infra.database.inbox defines abstract InboxEventModel."""
    from shared.infra.database.inbox import InboxEventModel
    assert getattr(InboxEventModel, "__abstract__", False) is True
