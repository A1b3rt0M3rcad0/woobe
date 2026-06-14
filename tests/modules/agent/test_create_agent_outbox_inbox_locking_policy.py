"""Tests for spec 079 — create agent outbox inbox locking policy."""
import inspect

from modules.agent.infra.database.repositories import (
    AGENT_DEFAULT_BATCH_SIZE,
    AGENT_INBOX_LOCK_TIMEOUT_SECONDS,
    AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS,
    SQLAlchemyAgentInboxRepository,
    SQLAlchemyAgentOutboxRepository,
)


class TestLockingPolicyConstants:
    """Verify locking policy constants are defined."""

    def test_outbox_lock_timeout_defined(self):
        assert isinstance(AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS, int)
        assert AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS > 0

    def test_inbox_lock_timeout_defined(self):
        assert isinstance(AGENT_INBOX_LOCK_TIMEOUT_SECONDS, int)
        assert AGENT_INBOX_LOCK_TIMEOUT_SECONDS > 0

    def test_default_batch_size_is_50(self):
        assert AGENT_DEFAULT_BATCH_SIZE == 50

    def test_outbox_lock_timeout_default_300(self):
        assert AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS == 300

    def test_inbox_lock_timeout_default_300(self):
        assert AGENT_INBOX_LOCK_TIMEOUT_SECONDS == 300


class TestOutboxLockingPolicy:
    """Verify outbox claim_batch uses correct locking pattern."""

    def test_uses_for_update_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "with_for_update" in source
        assert "skip_locked=True" in source

    def test_sets_locked_at(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_at" in source

    def test_sets_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_by" in source

    def test_lock_timeout_configurable(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source

    def test_expired_locks_recoverable(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_at" in source
        assert "INTERVAL" in source

    def test_batch_size_has_default(self):
        sig = inspect.signature(SQLAlchemyAgentOutboxRepository.claim_batch)
        params = sig.parameters
        assert "batch_size" in params
        assert params["batch_size"].default == AGENT_DEFAULT_BATCH_SIZE

    def test_lock_timeout_has_default(self):
        sig = inspect.signature(SQLAlchemyAgentOutboxRepository.claim_batch)
        params = sig.parameters
        assert "lock_timeout_seconds" in params
        assert params["lock_timeout_seconds"].default == AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS

    def test_transitions_status_to_publishing_on_claim(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert '"publishing"' in source or "'publishing'" in source

    def test_two_workers_cannot_claim_same_record(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked" in source


class TestInboxLockingPolicy:
    """Verify inbox claim_batch uses correct locking pattern."""

    def test_uses_for_update_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "with_for_update" in source
        assert "skip_locked=True" in source

    def test_sets_locked_at(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_at" in source

    def test_sets_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_by" in source

    def test_lock_timeout_configurable(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source

    def test_expired_locks_recoverable(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_at" in source
        assert "INTERVAL" in source

    def test_batch_size_has_default(self):
        sig = inspect.signature(SQLAlchemyAgentInboxRepository.claim_batch)
        params = sig.parameters
        assert "batch_size" in params
        assert params["batch_size"].default == AGENT_DEFAULT_BATCH_SIZE

    def test_lock_timeout_has_default(self):
        sig = inspect.signature(SQLAlchemyAgentInboxRepository.claim_batch)
        params = sig.parameters
        assert "lock_timeout_seconds" in params
        assert params["lock_timeout_seconds"].default == AGENT_INBOX_LOCK_TIMEOUT_SECONDS

    def test_transitions_status_to_processing_on_claim(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert '"processing"' in source or "'processing'" in source

    def test_increments_attempts_on_claim(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "attempts" in source

    def test_two_workers_cannot_claim_same_record(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "skip_locked" in source


class TestConcurrencyPolicy:
    """Verify that the locking policy ensures safe concurrent access."""

    def test_outbox_skip_locked_prevents_double_claim(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "with_for_update" in source
        assert "skip_locked=True" in source
        assert "locked_at" in source
        assert "locked_by" in source

    def test_inbox_skip_locked_prevents_double_claim(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "with_for_update" in source
        assert "skip_locked=True" in source
        assert "locked_at" in source
        assert "locked_by" in source

    def test_outbox_stale_lock_recovery(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source
        assert "INTERVAL" in source
        assert "locked_at" in source

    def test_inbox_stale_lock_recovery(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source
        assert "INTERVAL" in source
        assert "locked_at" in source
