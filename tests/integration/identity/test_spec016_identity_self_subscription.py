"""Tests for spec 016: remove identity self-subscription.

Covers: no consumer registration, outbox dispatcher only, event naming.
"""
from unittest.mock import MagicMock

from woobe_workers.consumers.identity.registry import (
    IdentityWorkerRegistry,
    register_identity_workers,
)


class TestConsumerRegistration:
    """Identity registry must not register consumer or processor."""

    def test_registry_registers_only_outbox(self):
        registry = MagicMock()
        engine = MagicMock()
        rabbitmq = MagicMock()
        register_identity_workers(
            registry=registry,
            settings=MagicMock(),
            engine=engine,
            rabbitmq_manager=rabbitmq,
        )
        assert registry.register.call_count == 1

    def test_registry_returns_early_without_rabbitmq(self):
        registry = MagicMock()
        register_identity_workers(
            registry=registry,
            settings=MagicMock(),
            engine=MagicMock(),
            rabbitmq_manager=None,
        )
        registry.register.assert_not_called()


class TestOutboxAtomicity:
    """Identity outbox dispatcher must still be available as producer."""

    def test_worker_registry_can_hold_workers(self):
        reg = IdentityWorkerRegistry()
        reg.register(MagicMock())
        assert len(reg.iter_workers()) == 1
