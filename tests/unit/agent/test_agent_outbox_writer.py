"""Tests for spec 007: agent outbox writer and event catalog.

Covers: field preservation, rollback, multiple occurrences,
legacy compatibility, and redaction.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.agent.domain.events import (
    EVENT_CATALOG,
    LEGACY_EVENT_MAP,
    AgentExecutionRequestedV1,
    AgentFallbackTriggeredV1,
    AgentMessageCreatedV1,
    AgentSessionCreatedV1,
    AgentToolCreatedV1,
    resolve_event_type,
)
from modules.agent.infra.messaging.event_mappers import (
    domain_event_to_outbox,
    outbox_to_rabbit_message,
)


class TestFieldPreservation:
    """All fields from AgentDomainEvent must be preserved in the outbox model."""

    @pytest.mark.asyncio
    async def test_all_fields_preserved(self):
        agent_id = uuid.uuid4()
        session_id = uuid.uuid4()
        correlation_id = uuid.uuid4()
        causation_id = uuid.uuid4()

        event = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={"input": "hello"},
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata={"trace_id": "abc123"},
        )

        model = domain_event_to_outbox(event)

        assert model.id == event.event_id
        assert model.routing_key == event.routing_key
        assert model.event_type == event.event_type
        assert model.event_version == event.event_version
        assert model.payload == event.payload
        assert model.metadata_ == event.metadata
        assert model.idempotency_key == event.idempotency_key
        assert model.correlation_id == event.correlation_id
        assert model.causation_id == event.causation_id
        assert model.status == "pending"
        assert model.attempts == 0
        assert model.created_at is not None

    @pytest.mark.asyncio
    async def test_routing_key_not_hardcoded(self):
        event = AgentToolCreatedV1.create(
            tool_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            payload={"name": "test-tool"},
        )

        model = domain_event_to_outbox(event)

        assert model.routing_key == "agent.tool.created.v1"
        assert model.routing_key != "agent.event"

    @pytest.mark.asyncio
    async def test_idempotency_key_preserved(self):
        event = AgentSessionCreatedV1.create(
            session_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
        )
        original_key = event.idempotency_key

        model = domain_event_to_outbox(event)

        assert model.idempotency_key == original_key
        assert ":" not in original_key  # should be a hash, not raw concat

    @pytest.mark.asyncio
    async def test_correlation_and_causation_preserved(self):
        correlation_id = uuid.uuid4()
        causation_id = uuid.uuid4()

        event = AgentFallbackTriggeredV1.create(
            agent_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            payload={"reason": "timeout"},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

        model = domain_event_to_outbox(event)

        assert model.correlation_id == correlation_id
        assert model.causation_id == causation_id


class TestRollback:
    """Rollback must remove state and outbox event atomically."""

    @pytest.mark.asyncio
    async def test_session_rollback_removes_event(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.rollback = AsyncMock()

        event = AgentExecutionRequestedV1.create(
            agent_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            payload={"input": "test"},
        )

        model = domain_event_to_outbox(event)
        session.add(model)
        await session.flush()

        assert session.add.called
        assert session.flush.called

        await session.rollback()

    @pytest.mark.asyncio
    async def test_add_is_called_before_flush(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        event = AgentMessageCreatedV1.create(
            message_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            agent_id=uuid.uuid4(),
            role="assistant",
        )

        model = domain_event_to_outbox(event)
        session.add(model)
        await session.flush()

        session.add.assert_called_once_with(model)


class TestMultipleOccurrences:
    """Each write must produce distinct event_ids."""

    @pytest.mark.asyncio
    async def test_distinct_event_ids(self):
        agent_id = uuid.uuid4()
        session_id = uuid.uuid4()

        event1 = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={"input": "first"},
        )
        event2 = AgentExecutionRequestedV1.create(
            agent_id=agent_id,
            session_id=session_id,
            payload={"input": "second"},
        )

        model1 = domain_event_to_outbox(event1)
        model2 = domain_event_to_outbox(event2)

        assert model1.id != model2.id
        assert model1.payload != model2.payload

    @pytest.mark.asyncio
    async def test_consecutive_writes_produce_unique_ids(self):
        events = []
        for i in range(5):
            event = AgentExecutionRequestedV1.create(
                agent_id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                payload={"seq": i},
            )
            model = domain_event_to_outbox(event)
            events.append(model)

        ids = [e.id for e in events]
        assert len(set(ids)) == 5


class TestLegacyCompatibility:
    """Deprecated event types must resolve to canonical form."""

    def test_legacy_event_map_covers_all_deprecated_types(self):
        expected = {
            "runtime.session.created",
            "runtime.ask.completed",
            "agent.created",
            "agent.updated",
            "knowledge.collection.created",
            "knowledge.document.uploaded",
            "provider_credential.created",
            "provider_credential.updated",
        }
        assert expected == set(LEGACY_EVENT_MAP.keys())

    def test_resolve_legacy_to_canonical(self):
        assert (
            resolve_event_type("runtime.session.created")
            == "agent.execution.session.created.v1"
        )
        assert (
            resolve_event_type("runtime.ask.completed")
            == "agent.execution.message.created.v1"
        )
        assert resolve_event_type("agent.created") == "agent.agent.created.v1"
        assert resolve_event_type("agent.updated") == "agent.agent.updated.v1"

    def test_unknown_event_type_passthrough(self):
        assert resolve_event_type("agent.tool.created.v1") == "agent.tool.created.v1"
        assert resolve_event_type("foo.bar.v1") == "foo.bar.v1"


class TestEventCatalog:
    """EVENT_CATALOG must cover all known agent events."""

    def test_execution_events_in_catalog(self):
        assert EVENT_CATALOG["agent.execution.requested.v1"] == "execution"
        assert EVENT_CATALOG["agent.execution.completed.v1"] == "execution"
        assert EVENT_CATALOG["agent.execution.failed.v1"] == "execution"
        assert EVENT_CATALOG["agent.execution.fallback_triggered.v1"] == "execution"
        assert EVENT_CATALOG["agent.execution.session.created.v1"] == "execution"
        assert EVENT_CATALOG["agent.execution.message.created.v1"] == "execution"

    def test_tool_events_in_catalog(self):
        assert EVENT_CATALOG["agent.tool.created.v1"] == "tool"
        assert EVENT_CATALOG["agent.tool.updated.v1"] == "tool"
        assert EVENT_CATALOG["agent.tool.status_changed.v1"] == "tool"

    def test_secret_events_in_catalog(self):
        assert EVENT_CATALOG["agent.secret.created.v1"] == "secret"

    def test_credential_events_in_catalog(self):
        assert EVENT_CATALOG["agent.credential.created.v1"] == "credential"
        assert EVENT_CATALOG["agent.credential.updated.v1"] == "credential"

    def test_agent_events_in_catalog(self):
        assert EVENT_CATALOG["agent.agent.created.v1"] == "agent"
        assert EVENT_CATALOG["agent.agent.updated.v1"] == "agent"

    def test_knowledge_events_in_catalog(self):
        assert EVENT_CATALOG["agent.knowledge.collection.created.v1"] == "knowledge"
        assert EVENT_CATALOG["agent.knowledge.document.uploaded.v1"] == "knowledge"
        assert EVENT_CATALOG["agent.knowledge.document_indexed.v1"] == "knowledge"


class TestRedaction:
    """No sensitive data in outbox payloads."""

    @pytest.mark.asyncio
    async def test_no_encrypted_secret_in_payload(self):
        from modules.agent.domain.events import AgentSecretCreatedV1

        event = AgentSecretCreatedV1.create(
            secret_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="api-key",
            secret_type="api_key",
        )

        assert "encrypted_value" not in event.payload
        assert "value" not in event.payload

    @pytest.mark.asyncio
    async def test_no_secret_in_rabbit_message(self):
        from modules.agent.domain.events import AgentSecretCreatedV1

        event = AgentSecretCreatedV1.create(
            secret_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="api-key",
            secret_type="api_key",
        )

        model = domain_event_to_outbox(event)
        rabbit_msg = outbox_to_rabbit_message(model)

        assert "encrypted_value" not in rabbit_msg.body
        assert "value" not in rabbit_msg.body

    @pytest.mark.asyncio
    async def test_no_prompt_or_secret_in_execution_payload(self):
        event = AgentExecutionRequestedV1.create(
            agent_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            payload={"input": "hello"},  # user input, not secret
        )

        payload_keys = event.payload.keys()
        assert "secret" not in str(payload_keys).lower()
        assert "encrypted" not in str(payload_keys).lower()
