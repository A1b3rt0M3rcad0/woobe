from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.network.application.service import NetworkApplicationService


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Session:
    def __init__(self, execution) -> None:
        self.execution = execution
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return _Transaction()

    async def get(self, _model, execution_id, **_kwargs):
        return self.execution if execution_id == self.execution.id else None

    def add(self, value) -> None:
        self.added.append(value)


class _SessionFactory:
    def __init__(self, session) -> None:
        self.session = session

    def __call__(self):
        return self.session


class _RuntimeControl:
    def __init__(self, snapshots) -> None:
        self.snapshots = list(snapshots)
        self.requested = []

    async def snapshot(self, _execution_id):
        if self.snapshots:
            return self.snapshots.pop(0)
        return None

    async def request_cancel(self, execution_id) -> None:
        self.requested.append(execution_id)


@pytest.mark.asyncio
async def test_cancel_queued_network_execution_terminalizes_before_worker_start() -> None:
    execution = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        network_session_id=uuid4(),
        status="queued",
        cancel_requested_at=None,
        completed_at=None,
        last_event_sequence=1,
    )
    session = _Session(execution)
    runtime = _RuntimeControl([None, None])
    service = NetworkApplicationService(
        _SessionFactory(session),
        runtime_control=runtime,
    )

    await service.request_cancellation(execution.id, execution.project_id)

    assert execution.status == "cancelled"
    assert execution.cancel_requested_at is not None
    assert execution.completed_at is not None
    assert execution.last_event_sequence == 2
    assert runtime.requested == []
    assert len(session.added) == 1
    event = session.added[0]
    assert event.network_execution_id == execution.id
    assert event.network_session_id == execution.network_session_id
    assert event.sequence == 2
    assert event.event_type == "execution_cancelled"
    assert event.payload == {"cancelled_before_start": True}


@pytest.mark.asyncio
async def test_cancel_live_network_execution_uses_runtime_control_without_rewriting_durable_status() -> None:
    execution = SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        network_session_id=uuid4(),
        status="queued",
        cancel_requested_at=None,
        completed_at=None,
        last_event_sequence=1,
    )
    session = _Session(execution)
    runtime = _RuntimeControl([{"status": "running", "phase": "network_execution"}])
    service = NetworkApplicationService(
        _SessionFactory(session),
        runtime_control=runtime,
    )

    await service.request_cancellation(execution.id, execution.project_id)

    assert runtime.requested == [execution.id]
    assert execution.status == "queued"
    assert execution.cancel_requested_at is None
    assert execution.completed_at is None
    assert execution.last_event_sequence == 1
    assert session.added == []
