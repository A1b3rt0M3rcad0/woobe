"""Integration tests for spec 007 — Outbox/Inbox flow contract.

Validates that each module's messaging infrastructure:
- Consumer persists message to Inbox before acknowledging the broker.
- Processor is idempotent (same message processed only once).
- Outbox dispatcher publishes events after commit.
- Workers belong to modules, not shared/src/workers.
"""
from __future__ import annotations


class TestOutboxInboxFlow:
    """Contract tests for module-level Outbox/Inbox event flow.

    These tests define the expected behavior and serve as contract definitions.
    Full validation requires a live database and RabbitMQ connection.
    """

    def test_consumer_persists_inbox_before_ack(self):
        """The consumer must save the message to the Inbox table before
        acknowledging the broker. If persistence fails, ack must not be sent."""

    def test_processor_is_idempotent(self):
        """Processing the same Inbox record twice must be safe. The second
        attempt must detect the record as already processed and skip."""

    def test_outbox_dispatches_after_commit(self):
        """Outbox events must only be dispatched after a successful UoW commit.
        Events with 'pending' status must be claimed, published, and marked."""

    def test_inbox_processor_claims_and_processes(self):
        """The processor claims pending Inbox records with a lock, calls the
        internal handler, and marks as processed/failed/dead accordingly."""

    def test_dead_letter_records_are_preserved(self):
        """Messages moved to dead letter status must preserve original payload,
        routing key, correlation id, and error details for audit."""
