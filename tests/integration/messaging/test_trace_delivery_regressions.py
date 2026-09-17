from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from modules.agent.domain.events import (
    AgentExecutionCompletedV1,
    AgentExecutionToolCompletedV1,
)
from modules.agent.infra.messaging.event_mappers import domain_event_to_outbox
from modules.agent.infra.messaging.publishers import AgentRabbitMQPublisher
from woobe_api.http.agent.controllers.ask_agent_stream_controller import (
    commit_safe_stream,
)
from modules.observability.infra.messaging.event_mappers import (
    rabbit_message_to_inbox,
)
from modules.observability.infra.messaging.inbox_handlers import HANDLER_MAP
from woobe_workers.consumers.observability.inbox_consumer import (
    OBSERVABILITY_INBOX_ROUTING_KEYS,
)


def _runtime_sse(
    event_type: str,
    *,
    sequence: int,
    run_id: UUID,
    session_id: UUID,
    payload: dict,
) -> str:
    envelope = {
        "protocol_version": 2,
        "event_id": str(uuid4()),
        "run_id": str(run_id),
        "session_id": str(session_id),
        "run_kind": "AGENT",
        "sequence": sequence,
        "type": event_type,
        "occurred_at": "2026-09-17T00:00:00+00:00",
        "payload": payload,
    }
    return (
        f"id: {sequence}\n"
        f"event: {event_type}\n"
        f"data: {json.dumps(envelope)}\n\n"
    )


def test_execution_idempotency_is_scoped_to_trace_not_session() -> None:
    agent_id = uuid4()
    session_id = uuid4()

    first = AgentExecutionCompletedV1.create(
        agent_id=agent_id,
        session_id=session_id,
        payload={"trace_id": str(uuid4())},
    )
    second = AgentExecutionCompletedV1.create(
        agent_id=agent_id,
        session_id=session_id,
        payload={"trace_id": str(uuid4())},
    )

    assert domain_event_to_outbox(first).idempotency_key != domain_event_to_outbox(second).idempotency_key


def test_multiple_tool_events_in_one_trace_do_not_collide() -> None:
    agent_id = uuid4()
    session_id = uuid4()
    trace_id = uuid4()

    first = AgentExecutionToolCompletedV1.create(
        agent_id=agent_id,
        session_id=session_id,
        payload={"trace_id": str(trace_id), "tool_name": "search"},
    )
    second = AgentExecutionToolCompletedV1.create(
        agent_id=agent_id,
        session_id=session_id,
        payload={"trace_id": str(trace_id), "tool_name": "search"},
    )

    assert domain_event_to_outbox(first).idempotency_key != domain_event_to_outbox(second).idempotency_key


def test_observability_mapper_converts_origin_id_to_uuid() -> None:
    event_id = uuid4()
    correlation_id = uuid4()
    message = SimpleNamespace(
        body=json.dumps(
            {
                "event_id": str(event_id),
                "event_type": "agent.execution.requested.v1",
                "event_version": 1,
                "producer_module": "agent",
                "routing_key": "agent.execution.requested.v1",
                "payload": {"trace_id": str(uuid4()), "project_id": str(uuid4())},
                "idempotency_key": "event-key",
                "correlation_id": str(correlation_id),
                "causation_id": None,
            }
        ).encode(),
        routing_key="agent.execution.requested.v1",
        message_id=str(event_id),
        headers={},
    )

    inbox = rabbit_message_to_inbox(message)

    assert inbox.outbox_origin_id == event_id
    assert isinstance(inbox.outbox_origin_id, UUID)
    assert inbox.message_id == str(event_id)


def test_observability_consumes_and_handles_requested_event() -> None:
    event_type = "agent.execution.requested.v1"
    assert event_type in OBSERVABILITY_INBOX_ROUTING_KEYS
    assert event_type in HANDLER_MAP


@pytest.mark.asyncio
async def test_done_is_exposed_only_after_source_generator_finishes() -> None:
    run_id = uuid4()
    session_id = uuid4()

    class FakeService:
        committed = False

        async def stream(self, _input):
            yield _runtime_sse(
                "token",
                sequence=1,
                run_id=run_id,
                session_id=session_id,
                payload={
                    "content": "ok",
                    "visibility": "assistant",
                    "channel": "final",
                    "phase": "response_generation",
                },
            )
            yield _runtime_sse(
                "done",
                sequence=2,
                run_id=run_id,
                session_id=session_id,
                payload={"trace_id": "trace"},
            )
            self.committed = True

    service = FakeService()
    stream = commit_safe_stream(service, object())

    first = await anext(stream)
    assert '"token"' in first
    assert '"content": "ok"' in first
    assert service.committed is False

    second = await anext(stream)
    assert service.committed is True
    assert '"done"' in second


@pytest.mark.asyncio
async def test_internal_v2_token_is_not_exposed_by_commit_safe_stream() -> None:
    run_id = uuid4()
    session_id = uuid4()

    class FakeService:
        async def stream(self, _input):
            yield _runtime_sse(
                "token",
                sequence=1,
                run_id=run_id,
                session_id=session_id,
                payload={
                    "content": "hidden",
                    "visibility": "internal",
                    "channel": "reasoning",
                    "phase": "response_generation",
                },
            )
            yield _runtime_sse(
                "done",
                sequence=2,
                run_id=run_id,
                session_id=session_id,
                payload={"answer": "public"},
            )

    chunks = [chunk async for chunk in commit_safe_stream(FakeService(), object())]

    assert len(chunks) == 1
    assert '"done"' in chunks[0]
    assert "hidden" not in chunks[0]


@pytest.mark.asyncio
async def test_finalization_error_discards_pending_done() -> None:
    run_id = uuid4()
    session_id = uuid4()

    class FakeService:
        async def stream(self, _input):
            yield _runtime_sse(
                "done",
                sequence=1,
                run_id=run_id,
                session_id=session_id,
                payload={"trace_id": "trace"},
            )
            yield _runtime_sse(
                "error",
                sequence=2,
                run_id=run_id,
                session_id=session_id,
                payload={"message": "commit failed"},
            )

    chunks = [chunk async for chunk in commit_safe_stream(FakeService(), object())]

    assert len(chunks) == 1
    assert '"error"' in chunks[0]
    assert all('"done"' not in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_agent_publisher_raises_when_confirm_is_false() -> None:
    class Exchange:
        async def publish(self, **_kwargs):
            return False

    manager = SimpleNamespace(exchange=Exchange())
    publisher = AgentRabbitMQPublisher(manager)
    envelope = SimpleNamespace(
        body="{}",
        correlation_id=str(uuid4()),
        headers={},
        message_id=str(uuid4()),
        routing_key="agent.execution.completed.v1",
    )

    with pytest.raises(RuntimeError, match="did not confirm"):
        await publisher.publish(envelope)
