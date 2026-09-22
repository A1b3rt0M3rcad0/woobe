from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkSessionModel,
)
from modules.network.infra.runtime.run_event_projector import NetworkRunEventProjector
from shared.contracts.run_event_journal import DurableRunEvent
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


class _Session:
    def __init__(self, state) -> None:
        self.state = state

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @asynccontextmanager
    async def begin(self):
        yield self

    async def get(self, model, object_id, **kwargs):
        del kwargs
        if model is NetworkExecutionModel:
            return (
                self.state.execution
                if self.state.execution.id == object_id
                else None
            )
        if model is NetworkSessionModel:
            return (
                self.state.network_session
                if self.state.network_session.id == object_id
                else None
            )
        if model is NetworkMessageModel:
            return self.state.messages.get(object_id)
        raise AssertionError(f"Unexpected model: {model}")

    def add(self, value) -> None:
        if isinstance(value, NetworkMessageModel):
            self.state.messages[value.id] = value


class _SessionFactory:
    def __init__(self, state) -> None:
        self.state = state

    def __call__(self):
        return _Session(self.state)


class _UnusedJournal:
    pass


class _UnusedFinalizer:
    pass


def _state():
    execution_id = uuid4()
    session_id = uuid4()
    project_id = uuid4()
    execution = SimpleNamespace(
        id=execution_id,
        network_session_id=session_id,
        project_id=project_id,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        journal_projected_sequence=0,
    )
    network_session = SimpleNamespace(
        id=session_id,
        last_message_at=None,
    )
    return SimpleNamespace(
        execution=execution,
        network_session=network_session,
        messages={},
    )


def _event(state, *, message_id, sequence=1):
    return DurableRunEvent(
        run_id=state.execution.id,
        session_id=state.network_session.id,
        run_kind="network",
        sequence=sequence,
        event_id=str(uuid4()),
        event_type="assistant.message.completed",
        occurred_at="2026-09-22T12:00:00+00:00",
        schema_version=1,
        storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        metadata={"project_id": str(state.execution.project_id)},
        payload={
            "message_id": str(message_id),
            "content": "Vou procurar.",
            "phase": "capability_response_generation",
            "output_mode": "intermediate",
            "provider": "custom",
            "model": "deepseek-v4-flash",
            "partial": False,
            "completed_at": "2026-09-22T12:00:01+00:00",
        },
    )


@pytest.mark.asyncio
async def test_network_projector_materializes_root_intermediate_message() -> None:
    state = _state()
    message_id = uuid4()
    projector = NetworkRunEventProjector(
        _SessionFactory(state),
        journal=_UnusedJournal(),
        finalizer=_UnusedFinalizer(),
    )

    await projector.project([_event(state, message_id=message_id)])

    assert state.execution.journal_projected_sequence == 1
    assert list(state.messages) == [message_id]
    message = state.messages[message_id]
    assert message.network_session_id == state.network_session.id
    assert message.network_execution_id == state.execution.id
    assert message.project_id == state.execution.project_id
    assert message.role == "assistant"
    assert message.content == "Vou procurar."
    assert message.data == {
        "run_id": str(state.execution.id),
        "phase": "capability_response_generation",
        "output_mode": "intermediate",
        "provider": "custom",
        "model": "deepseek-v4-flash",
        "partial": False,
    }
    assert message.created_at == datetime(
        2026,
        9,
        22,
        12,
        0,
        1,
        tzinfo=timezone.utc,
    )
    assert state.network_session.last_message_at == message.created_at


@pytest.mark.asyncio
async def test_network_intermediate_projection_is_idempotent_by_message_id() -> None:
    state = _state()
    message_id = uuid4()
    projector = NetworkRunEventProjector(
        _SessionFactory(state),
        journal=_UnusedJournal(),
        finalizer=_UnusedFinalizer(),
    )
    event = _event(state, message_id=message_id)

    await projector.project([event])
    first = state.messages[message_id]

    # Simulate a crash after SQL commit but before the journal cursor commit.
    state.execution.journal_projected_sequence = 0
    await projector.project([event])

    assert list(state.messages) == [message_id]
    assert state.messages[message_id] is first
    assert state.execution.journal_projected_sequence == 1


@pytest.mark.asyncio
async def test_network_projector_ignores_non_intermediate_assistant_event() -> None:
    state = _state()
    message_id = uuid4()
    event = _event(state, message_id=message_id)
    event.payload["output_mode"] = "final"
    projector = NetworkRunEventProjector(
        _SessionFactory(state),
        journal=_UnusedJournal(),
        finalizer=_UnusedFinalizer(),
    )

    await projector.project([event])

    assert state.messages == {}
    assert state.execution.journal_projected_sequence == 1
