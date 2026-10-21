"""Behavioral tests for the Agent outbox dispatcher worker."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from modules.agent.domain.events import AgentExecutionRequestedV1
from modules.agent.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    domain_event_to_outbox,
    outbox_to_rabbit_message,
)
from woobe_workers.consumers.agent.outbox_dispatcher import (
    RETRY_BACKOFF_BASE_SECONDS,
    AgentOutboxDispatcherWorker,
    AgentOutboxPublisherProtocol,
)
from woobe_workers.runtime.outbox_dispatcher_base import BaseOutboxDispatcher
import woobe_workers.consumers.agent.outbox_dispatcher as dispatcher_module


class _RepositorySpy:
    def __init__(self, events=()):
        self.events = list(events)
        self.calls = []
        self.uows = []

    async def claim_batch(self, *, batch_size, locked_by):
        self.calls.append(("claim_batch", batch_size, locked_by))
        return self.events

    async def mark_published(self, event_id):
        self.calls.append(("mark_published", event_id))

    async def mark_dead(self, event_id, error):
        self.calls.append(("mark_dead", event_id, error))

    async def mark_retryable(self, event_id, error, available_at):
        self.calls.append(("mark_retryable", event_id, error, available_at))


class _PublisherSpy:
    def __init__(self, calls=None):
        self.envelopes = []
        self.calls = calls

    async def publish(self, envelope):
        self.envelopes.append(envelope)
        if self.calls is not None:
            self.calls.append(("publish", envelope))


def _event():
    return domain_event_to_outbox(
        AgentExecutionRequestedV1.create(
            agent_id=uuid4(),
            session_id=uuid4(),
            payload={"action": "dispatch"},
        )
    )


def _install_uow(monkeypatch, repository, calls=None):
    class UnitOfWork:
        def __init__(self, _engine):
            self.session = object()

        async def __aenter__(self):
            if calls is not None:
                calls.append(("uow_enter", self.session))
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if calls is not None:
                calls.append(("uow_exit", self.session))

    def make_repository(uow):
        repository.uows.append(uow)
        if calls is not None:
            calls.append(("repository", uow, uow.session))
        return repository

    monkeypatch.setattr(dispatcher_module, "AgentUnitOfWork", UnitOfWork)
    monkeypatch.setattr(
        dispatcher_module,
        "SQLAlchemyAgentOutboxRepository",
        make_repository,
    )


class TestOutboxDispatcherStructure:
    def test_file_exists_in_correct_location(self):
        import woobe_workers.consumers.agent.outbox_dispatcher as mod

        assert mod.__file__ is not None
        assert "packages/woobe-workers/src/woobe_workers/consumers/agent" in mod.__file__.replace("\\", "/")

    def test_inherits_from_base_and_implements_contract(self):
        assert issubclass(AgentOutboxDispatcherWorker, BaseOutboxDispatcher)
        for method in (
            "claim_pending",
            "publish",
            "mark_published",
            "mark_dead",
            "mark_retryable",
        ):
            assert callable(getattr(AgentOutboxDispatcherWorker, method, None))

    def test_protocol_has_publish_method(self):
        assert callable(AgentOutboxPublisherProtocol.publish)


class TestOutboxDispatcherBehavior:
    @pytest.mark.asyncio
    async def test_claim_publish_and_status_use_repository_publisher_and_uow(self, monkeypatch):
        event = _event()
        calls = []
        repository = _RepositorySpy([event])
        publisher = _PublisherSpy(calls)
        _install_uow(monkeypatch, repository, calls)
        worker = AgentOutboxDispatcherWorker(
            object(), publisher, worker_id="dispatcher-test"
        )

        await worker.run()

        envelope = outbox_to_rabbit_message(event)
        assert publisher.envelopes == [envelope]
        assert repository.calls == [
            ("claim_batch", worker.BATCH_SIZE, "dispatcher-test"),
            ("mark_published", event.id),
        ]
        assert [call[0] for call in calls] == [
            "uow_enter",
            "repository",
            "uow_exit",
            "publish",
            "uow_enter",
            "repository",
            "uow_exit",
        ]
        repositories = [call for call in calls if call[0] == "repository"]
        assert all(call[1].session is call[2] for call in repositories)
        assert repository.uows[0] is not repository.uows[1]

    @pytest.mark.asyncio
    async def test_publish_dispatches_the_envelope_created_for_claimed_record(self):
        publisher = _PublisherSpy()
        worker = AgentOutboxDispatcherWorker(object(), publisher)
        event = _event()
        record = worker._record(event)
        envelope = RabbitMQMessageEnvelope(
            routing_key=event.routing_key,
            body="serialized body",
            correlation_id=str(event.correlation_id),
            headers={"x-idempotency-key": event.idempotency_key},
        )
        worker._envelope_map[event.id] = envelope

        await worker.publish(record)

        assert publisher.envelopes == [envelope]

    @pytest.mark.asyncio
    async def test_retryable_status_schedules_backoff_through_repository(self, monkeypatch):
        repository = _RepositorySpy()
        _install_uow(monkeypatch, repository)
        worker = AgentOutboxDispatcherWorker(object(), _PublisherSpy())
        event_id = uuid4()
        from woobe_workers.runtime.outbox_dispatcher_base import OutboxRecord

        record = OutboxRecord(
            id=event_id,
            aggregate_type="agent",
            aggregate_id=uuid4(),
            event_type="agent.execution.requested.v1",
            event_version=1,
            payload={},
            attempts=2,
            error="broker unavailable",
        )
        before = datetime.now(timezone.utc)

        await worker.mark_retryable(record)

        after = datetime.now(timezone.utc)
        call = repository.calls[0]
        assert call[:3] == ("mark_retryable", event_id, "broker unavailable")
        expected_delay = timedelta(seconds=RETRY_BACKOFF_BASE_SECONDS * 3)
        assert before + expected_delay <= call[3] <= after + expected_delay

    @pytest.mark.asyncio
    async def test_claim_uses_worker_id_and_a_unit_of_work_session(self, monkeypatch):
        event = _event()
        repository = _RepositorySpy([event])
        calls = []
        _install_uow(monkeypatch, repository, calls)
        worker = AgentOutboxDispatcherWorker(
            object(), _PublisherSpy(), worker_id="claim-worker"
        )

        records = await worker.claim_pending(limit=7)

        assert len(records) == 1
        assert records[0].id == event.id
        assert repository.calls == [("claim_batch", 7, "claim-worker")]
        assert [call[0] for call in calls] == [
            "uow_enter", "repository", "uow_exit"
        ]
        assert calls[0][1] is calls[1][2]


class TestOutboxDispatcherModuleBoundary:
    def test_no_imports_from_other_modules(self):
        import woobe_workers.consumers.agent.outbox_dispatcher as mod

        tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "modules." in node.module:
                assert node.module.startswith("modules.agent"), (
                    f"Forbidden cross-module import: {node.module}"
                )
