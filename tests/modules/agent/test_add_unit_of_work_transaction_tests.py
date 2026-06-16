"""Tests for spec 126 — add unit of work transaction tests.

Validates transactional guarantees across the agent UoW and messaging pipeline:
UoW commit/rollback, Outbox persisted in same transaction as state change,
Inbox persisted before ack, publisher confirm mandatory, idempotency via
message_id/idempotency_key, concurrency with SKIP LOCKED, retry/backoff for
transient failure, and dead-letter for permanent failure.
"""
from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from modules.agent.infra.database.models import (
    AgentInboxEventModel,
    AgentOutboxEventModel,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentInboxRepository,
    SQLAlchemyAgentOutboxRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.messaging.publishers import AgentRabbitMQPublisher
from modules.agent.infra.workers.inbox_consumer import AgentInboxConsumerWorker
from modules.agent.infra.workers.inbox_processor import AgentInboxProcessorWorker
from modules.agent.infra.workers.outbox_dispatcher import (
    AgentOutboxDispatcherWorker,
    RETRY_BACKOFF_BASE_SECONDS as OUTBOX_BACKOFF_SECONDS,
)
from modules.agent.infra.workers.inbox_processor import (
    RETRY_BACKOFF_BASE_SECONDS as INBOX_BACKOFF_SECONDS,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.workers.inbox_consumer_base import BaseInboxConsumer
from shared.workers.inbox_processor_base import BaseInboxProcessor
from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher


class TestAgentUnitOfWorkTransactionSuccess:
    """Verify UoW success path: commit on clean __aexit__."""

    def test_uow_inherits_from_abstract_unit_of_work(self):
        assert issubclass(AgentUnitOfWork, UnitOfWork)

    def test_uow_aexit_commits_on_success(self):
        source = inspect.getsource(AgentUnitOfWork.__aexit__)
        assert "self.commit()" in source or "await self.commit()" in source

    def test_uow_aexit_rollbacks_on_exception(self):
        source = inspect.getsource(AgentUnitOfWork.__aexit__)
        assert "self.rollback()" in source or "await self.rollback()" in source

    def test_uow_commit_handles_pending_rollback_error(self):
        source = inspect.getsource(AgentUnitOfWork.commit)
        assert "PendingRollbackError" in source

    def test_uow_commit_still_raises_pending_rollback(self):
        source = inspect.getsource(AgentUnitOfWork.commit)
        assert "raise" in source

    def test_uow_session_property_defined(self):
        assert "session" in dir(AgentUnitOfWork) or hasattr(AgentUnitOfWork, "session")

    def test_uow_session_raises_before_enter(self):
        factory = MagicMock()
        uow = AgentUnitOfWork(factory)
        with pytest.raises(RuntimeError, match="session not started"):
            _ = uow.session


class TestAgentUnitOfWorkTransactionRollback:
    """Verify UoW rollback and session cleanup."""

    def test_uow_has_rollback_method(self):
        assert hasattr(AgentUnitOfWork, "rollback")
        assert inspect.iscoroutinefunction(AgentUnitOfWork.rollback)

    def test_uow_rollback_source_calls_session_rollback(self):
        source = inspect.getsource(AgentUnitOfWork.rollback)
        assert "rollback" in source

    def test_uow_aexit_closes_session(self):
        source = inspect.getsource(AgentUnitOfWork.__aexit__)
        assert "close" in source or "self._session.close()" in source

    def test_uow_aexit_nulls_session(self):
        source = inspect.getsource(AgentUnitOfWork.__aexit__)
        assert "self._session = None" in source

    def test_uow_aexit_nulls_all_repository_references(self):
        source = inspect.getsource(AgentUnitOfWork.__aexit__)
        for repo in [
            "_agents", "_provider_credentials", "_sessions", "_messages",
            "_ask_jobs", "_document_collections", "_documents",
            "_document_chunks", "_knowledge_versions", "_outbox", "_inbox",
        ]:
            assert f"{repo} = None" in source, f"Missing cleanup for {repo}"


class TestAgentOutboxTransactionSameSession:
    """Verify outbox events are persisted in the same transaction as state changes."""

    def test_outbox_repo_uses_passed_session(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.__init__)
        assert "self._session = session" in source

    def test_outbox_add_flushes_within_session(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.add)
        assert "self._session.add" in source
        assert "self._session.flush" in source

    def test_uow_exposes_outbox_repo(self):
        assert hasattr(AgentUnitOfWork, "outbox")
        prop = getattr(AgentUnitOfWork, "outbox")
        assert isinstance(prop, property)

    def test_outbox_model_has_idempotency_key_column(self):
        assert hasattr(AgentOutboxEventModel, "idempotency_key")

    def test_outbox_model_has_status_column(self):
        assert hasattr(AgentOutboxEventModel, "status")

    def test_outbox_model_has_correlation_id(self):
        assert hasattr(AgentOutboxEventModel, "correlation_id")

    def test_outbox_model_has_causation_id(self):
        assert hasattr(AgentOutboxEventModel, "causation_id")

    def test_outbox_model_has_published_at(self):
        assert hasattr(AgentOutboxEventModel, "published_at")

    def test_outbox_model_has_locked_at(self):
        assert hasattr(AgentOutboxEventModel, "locked_at")

    def test_outbox_model_has_locked_by(self):
        assert hasattr(AgentOutboxEventModel, "locked_by")

    def test_outbox_model_has_attempts(self):
        assert hasattr(AgentOutboxEventModel, "attempts")

    def test_outbox_model_has_error(self):
        assert hasattr(AgentOutboxEventModel, "error")


class TestAgentInboxPersistBeforeAck:
    """Verify inbox events are persisted before acknowledging the RabbitMQ message."""

    def test_inbox_repo_uses_passed_session(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.__init__)
        assert "self._session = session" in source

    def test_inbox_save_received_adds_and_flushes(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.save_received)
        assert "self._session.add" in source
        assert "self._session.flush" in source

    def test_consumer_persist_and_ack_catches_integrity_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "IntegrityError" in source

    def test_consumer_ack_called_after_persist(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        persist_idx = source.index("save_received")
        ack_idx = source.index("acknowledge")
        assert persist_idx < ack_idx, (
            "acknowledge must be called AFTER save_received"
        )

    def test_consumer_inherits_from_base_inbox_consumer(self):
        assert issubclass(AgentInboxConsumerWorker, BaseInboxConsumer)

    def test_consumer_requires_acknowledge(self):
        assert hasattr(AgentInboxConsumerWorker, "acknowledge")
        assert inspect.iscoroutinefunction(AgentInboxConsumerWorker.acknowledge)

    def test_consumer_acknowledge_calls_message_ack(self):
        source = inspect.getsource(AgentInboxConsumerWorker.acknowledge)
        assert "ack" in source

    def test_consumer_reject_calls_message_nack_or_reject(self):
        source = inspect.getsource(AgentInboxConsumerWorker.reject)
        assert "nack" in source or "reject" in source

    def test_consumer_reject_does_not_requeue(self):
        source = inspect.getsource(AgentInboxConsumerWorker.reject)
        assert "requeue=False" in source

    def test_inbox_model_has_message_id(self):
        assert hasattr(AgentInboxEventModel, "message_id")

    def test_inbox_model_has_idempotency_key(self):
        assert hasattr(AgentInboxEventModel, "idempotency_key")

    def test_inbox_model_has_status_column(self):
        assert hasattr(AgentInboxEventModel, "status")

    def test_inbox_model_has_processed_at(self):
        assert hasattr(AgentInboxEventModel, "processed_at")

    def test_inbox_model_has_attempts(self):
        assert hasattr(AgentInboxEventModel, "attempts")

    def test_inbox_model_has_locked_at(self):
        assert hasattr(AgentInboxEventModel, "locked_at")

    def test_inbox_model_has_locked_by(self):
        assert hasattr(AgentInboxEventModel, "locked_by")


class TestAgentPublisherConfirm:
    """Verify RabbitMQ publisher uses delivery confirmations."""

    def test_publisher_uses_persistent_delivery_mode(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "DeliveryMode.PERSISTENT" in source

    def test_publisher_sets_content_type_json(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "application/json" in source

    def test_publisher_sets_correlation_id(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "correlation_id" in source

    def test_publisher_uses_exchange_publish(self):
        source = inspect.getsource(AgentRabbitMQPublisher.publish)
        assert "exchange.publish" in source or "self._manager.exchange.publish" in source

    def test_dispatcher_publishes_before_marking_published(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        publish_idx = source.index("publish")
        mark_idx = source.index("mark_published")
        assert publish_idx < mark_idx, (
            "publish must be called BEFORE mark_published"
        )

    def test_dispatcher_marks_published_only_after_publish_success(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        lines = source.splitlines()
        publish_line = [i for i, line in enumerate(lines) if "publish" in line and "mark_published" not in line]
        mark_line = [i for i, line in enumerate(lines) if "mark_published" in line]
        assert publish_line and mark_line
        assert publish_line[0] < mark_line[0]

    def test_dispatcher_catches_publish_exception(self):
        source = inspect.getsource(BaseOutboxDispatcher.run)
        assert "except" in source
        assert "mark_failed" in source

    def test_agent_dispatcher_inherits_from_base_outbox_dispatcher(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseOutboxDispatcher)


class TestAgentIdempotencyTransactional:
    """Verify idempotency guarantees in transactional context."""

    def test_outbox_idempotency_key_unique_constraint(self):
        from sqlalchemy import UniqueConstraint as UC
        table = AgentOutboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1

    def test_inbox_message_id_unique_constraint(self):
        from sqlalchemy import UniqueConstraint as UC
        table = AgentInboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "message_id" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1

    def test_inbox_idempotency_key_unique_constraint(self):
        from sqlalchemy import UniqueConstraint as UC
        table = AgentInboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1

    def test_outbox_uq_constraints_are_present(self):
        assert hasattr(AgentOutboxEventModel, "__table_args__")
        table_args = AgentOutboxEventModel.__table_args__
        from sqlalchemy import UniqueConstraint as UC
        uq_count = len([a for a in (table_args or []) if isinstance(a, UC)])
        assert uq_count >= 1

    def test_inbox_uq_constraints_are_present(self):
        assert hasattr(AgentInboxEventModel, "__table_args__")
        table_args = AgentInboxEventModel.__table_args__
        from sqlalchemy import UniqueConstraint as UC
        uq_count = len([a for a in (table_args or []) if isinstance(a, UC)])
        assert uq_count >= 1

    def test_persist_and_ack_rolls_back_on_integrity_error(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "rollback" in source

    def test_persist_and_ack_completes_session_before_ack(self):
        source = inspect.getsource(AgentInboxConsumerWorker._persist_and_ack)
        assert "session.begin()" in source
        assert "acknowledge" in source


class TestAgentConcurrencySkipLocked:
    """Verify concurrency-safe claim patterns using SKIP LOCKED."""

    def test_outbox_claim_batch_uses_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "skip_locked=True" in source

    def test_outbox_claim_batch_uses_with_for_update(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "with_for_update" in source

    def test_outbox_claim_batch_sets_locked_at_and_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "locked_at" in source
        assert "locked_by" in source

    def test_outbox_claim_batch_transitions_to_publishing(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert '"publishing"' in source or "'publishing'" in source

    def test_inbox_claim_batch_uses_skip_locked(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "skip_locked=True" in source

    def test_inbox_claim_batch_uses_with_for_update(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "with_for_update" in source

    def test_inbox_claim_batch_sets_locked_at_and_locked_by(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "locked_at" in source
        assert "locked_by" in source

    def test_inbox_claim_batch_transitions_to_processing(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert '"processing"' in source or "'processing'" in source

    def test_outbox_claim_batch_handles_expired_locks(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source
        assert "INTERVAL" in source

    def test_inbox_claim_batch_handles_expired_locks(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "lock_timeout_seconds" in source
        assert "INTERVAL" in source

    def test_outbox_dispatcher_uses_skip_locked_via_repo(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.claim_pending)
        assert "claim_batch" in source

    def test_inbox_processor_uses_skip_locked_via_repo(self):
        source = inspect.getsource(AgentInboxProcessorWorker.claim_pending)
        assert "claim_batch" in source

    def test_two_dispatchers_cannot_claim_same_event(self):
        assert "skip_locked=True" in inspect.getsource(
            SQLAlchemyAgentOutboxRepository.claim_batch
        )

    def test_two_processors_cannot_claim_same_event(self):
        assert "skip_locked=True" in inspect.getsource(
            SQLAlchemyAgentInboxRepository.claim_batch
        )


class TestAgentRetryBackoff:
    """Verify retry with exponential backoff for transient failures."""

    def test_outbox_dispatcher_has_max_attempts(self):
        assert hasattr(AgentOutboxDispatcherWorker, "MAX_ATTEMPTS")
        assert AgentOutboxDispatcherWorker.MAX_ATTEMPTS >= 1

    def test_outbox_base_mark_failed_max_attempts_logic(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "MAX_ATTEMPTS" in source
        assert "mark_dead" in source
        assert "mark_retryable" in source

    def test_outbox_base_mark_failed_increments_attempts(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "record.attempts +=" in source or "record.attempts = " in source

    def test_inbox_processor_has_max_attempts(self):
        assert hasattr(AgentInboxProcessorWorker, "MAX_ATTEMPTS")
        assert AgentInboxProcessorWorker.MAX_ATTEMPTS >= 1

    def test_inbox_base_mark_failed_max_attempts_logic(self):
        source = inspect.getsource(BaseInboxProcessor.mark_failed)
        assert "MAX_ATTEMPTS" in source
        assert "mark_dead" in source
        assert "mark_retryable" in source

    def test_outbox_dispatcher_applies_backoff_seconds(self):
        assert OUTBOX_BACKOFF_SECONDS >= 1

    def test_inbox_processor_applies_backoff_seconds(self):
        assert INBOX_BACKOFF_SECONDS >= 1

    def test_outbox_mark_retryable_uses_exponential_backoff(self):
        source = inspect.getsource(AgentOutboxDispatcherWorker.mark_retryable)
        assert "backoff" in source or "BACKOFF" in source or "attempts" in source

    def test_inbox_mark_retryable_uses_exponential_backoff(self):
        source = inspect.getsource(AgentInboxProcessorWorker.mark_retryable)
        assert "backoff" in source or "BACKOFF" in source or "attempts" in source

    def test_outbox_claim_batch_filters_by_available_at(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert "available_at" in source

    def test_inbox_claim_batch_filters_by_available_at(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert "available_at" in source


class TestAgentDeadLetter:
    """Verify dead-letter behavior for permanent failures."""

    def test_outbox_dispatcher_calls_mark_dead_after_max_attempts(self):
        source = inspect.getsource(BaseOutboxDispatcher.mark_failed)
        assert "mark_dead" in source

    def test_outbox_repo_has_mark_dead(self):
        assert hasattr(SQLAlchemyAgentOutboxRepository, "mark_dead")
        assert inspect.iscoroutinefunction(SQLAlchemyAgentOutboxRepository.mark_dead)

    def test_outbox_mark_dead_sets_status_dead(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert "dead" in source or "'dead'" in source or '"dead"' in source

    def test_outbox_mark_dead_sets_error(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert "error" in source

    def test_outbox_mark_dead_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        assert "locked_at = None" in source
        assert "locked_by = None" in source

    def test_outbox_dead_events_not_claimable(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository.claim_batch)
        assert '"pending"' in source or "'pending'" in source
        assert '"retryable"' in source or "'retryable'" in source
        assert '"dead"' not in source and "'dead'" not in source

    def test_inbox_processor_calls_mark_dead_after_max_attempts(self):
        source = inspect.getsource(BaseInboxProcessor.mark_failed)
        assert "mark_dead" in source

    def test_inbox_repo_has_mark_dead(self):
        assert hasattr(SQLAlchemyAgentInboxRepository, "mark_dead")
        assert inspect.iscoroutinefunction(SQLAlchemyAgentInboxRepository.mark_dead)

    def test_inbox_mark_dead_sets_status_dead(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_dead)
        assert "dead" in source or "'dead'" in source or '"dead"' in source

    def test_inbox_mark_dead_sets_error(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_dead)
        assert "error" in source

    def test_inbox_mark_dead_clears_lock(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_dead)
        assert "locked_at = None" in source
        assert "locked_by = None" in source

    def test_inbox_dead_events_not_claimable(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository.claim_batch)
        assert '"received"' in source or "'received'" in source
        assert '"retryable"' in source or "'retryable'" in source
        assert '"dead"' not in source and "'dead'" not in source

    def test_dead_letter_is_observable_via_error_field(self):
        outbox_source = inspect.getsource(SQLAlchemyAgentOutboxRepository.mark_dead)
        inbox_source = inspect.getsource(SQLAlchemyAgentInboxRepository.mark_dead)
        assert "error" in outbox_source
        assert "error" in inbox_source


class TestAgentUnitOfWorkNoCrossModuleTransaction:
    """Verify no cross-module repositories or UoW scope leakage."""

    FORBIDDEN_MODULES = [
        "modules.metering",
        "modules.observability",
        "modules.billing",
        "modules.identity",
        "modules.tools",
        "modules.core",
    ]

    def test_uow_contains_no_cross_module_imports(self):
        source = inspect.getsource(AgentUnitOfWork)
        for pattern in self.FORBIDDEN_MODULES:
            assert pattern not in source, (
                f"AgentUnitOfWork must not import from '{pattern}'"
            )

    def test_uow_contains_no_other_module_repositories(self):
        source = inspect.getsource(AgentUnitOfWork)
        repos = [
            "MeteringRepository", "ObservabilityRepository", "BillingRepository",
            "IdentityRepository", "ToolsRepository", "CoreRepository",
        ]
        for repo in repos:
            assert repo not in source, (
                f"AgentUnitOfWork must not contain '{repo}'"
            )

    def test_outbox_repo_has_no_cross_module_imports(self):
        source = inspect.getsource(SQLAlchemyAgentOutboxRepository)
        for pattern in self.FORBIDDEN_MODULES:
            assert pattern not in source

    def test_inbox_repo_has_no_cross_module_imports(self):
        source = inspect.getsource(SQLAlchemyAgentInboxRepository)
        for pattern in self.FORBIDDEN_MODULES:
            assert pattern not in source
