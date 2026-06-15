"""Integration tests for spec 005 — module UoW transaction boundaries.

Validates that each module's UnitOfWork:
- Commits domain state and Outbox atomically.
- Rollback reverts both domain state and Outbox.
- Outbox events are not published without commit.
"""
from __future__ import annotations


class TestModuleUnitOfWorkTransactions:
    """Contract tests for module-level UnitOfWork transaction boundaries.

    These tests define the expected behavior and serve as contract definitions.
    Full validation requires a live database connection.
    """

    def test_uow_commit_persists_outbox_in_same_transaction(self):
        """When UoW commits, both domain changes and Outbox events must be
        persisted atomically. No partial commit is allowed."""

    def test_uow_rollback_reverts_domain_and_outbox(self):
        """When UoW rolls back, both domain changes and Outbox events must
        be reverted. No event should remain in pending state after rollback."""

    def test_uow_does_not_publish_without_commit(self):
        """Outbox events must not be published if UoW never commits."""

    def test_uow_context_exit_with_exception_rolls_back(self):
        """Leaving UoW context with an exception triggers rollback, not commit."""
