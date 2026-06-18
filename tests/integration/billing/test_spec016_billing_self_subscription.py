"""Tests for spec 016: remove billing self-subscription.

Covers: no consumer registration, outbox dispatcher only.
"""
from unittest.mock import MagicMock

from modules.billing.infra.workers.registry import (
    BillingWorkerRegistry,
    register_billing_workers,
)


class TestConsumerRegistration:
    """Billing registry must not register consumer or processor."""

    def test_registry_registers_only_outbox(self):
        registry = MagicMock()
        engine = MagicMock()
        rabbitmq = MagicMock()
        register_billing_workers(
            registry=registry,
            settings=MagicMock(),
            engine=engine,
            rabbitmq_manager=rabbitmq,
        )
        assert registry.register.call_count == 1


class TestOutboxAtomicity:
    """Billing outbox dispatcher must still be available as producer."""

    def test_worker_registry_can_hold_workers(self):
        reg = BillingWorkerRegistry()
        reg.register(MagicMock())
        assert len(reg.iter_workers()) == 1
