from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import modules.network.infra.runtime.finalizer as finalizer_module
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession(_AsyncContext):
    def __init__(self, execution) -> None:
        self.execution = execution

    def begin(self) -> _AsyncContext:
        return _AsyncContext()

    async def scalar(self, statement):
        del statement
        return self.execution


class _FakeNetworkRuntimeRepository:
    def __init__(self, session) -> None:
        del session

    async def mark_completed(
        self,
        execution,
        *,
        output: str,
        root_trace_id: UUID | None,
    ) -> None:
        del output, root_trace_id
        execution.status = "completed"
        execution.completed_at = datetime.now(timezone.utc)

    async def append_event(self, execution, event_type: str, payload: dict) -> None:
        del execution, event_type, payload


def _execution(*, created_at: datetime):
    return SimpleNamespace(
        id=uuid4(),
        status="queued",
        started_at=None,
        completed_at=None,
        created_at=created_at,
        resolved_bindings_snapshot={},
        draft_revision=1,
        network_session_id=uuid4(),
        project_id=uuid4(),
        last_event_sequence=0,
    )


@pytest.mark.asyncio
async def test_finalizer_materializes_network_start_from_earliest_invocation(
    monkeypatch,
) -> None:
    accepted_at = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    first_invocation_at = accepted_at + timedelta(seconds=3)
    later_invocation_at = accepted_at + timedelta(seconds=5)
    execution = _execution(created_at=accepted_at)

    monkeypatch.setattr(
        finalizer_module,
        "NetworkRuntimeRepository",
        _FakeNetworkRuntimeRepository,
    )
    finalizer = NetworkRuntimeFinalizer(lambda: _FakeSession(execution))

    finalized = await finalizer.finalize(
        execution_id=execution.id,
        version=None,
        invocation_states=[
            {"started_at": later_invocation_at.isoformat()},
            {"started_at": first_invocation_at.isoformat()},
        ],
        terminal_status="completed",
        output=None,
        trace_id=None,
    )

    assert finalized is True
    assert execution.started_at == first_invocation_at
    assert execution.started_at != accepted_at


@pytest.mark.asyncio
async def test_finalizer_falls_back_to_acceptance_when_no_invocation_started(
    monkeypatch,
) -> None:
    accepted_at = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
    execution = _execution(created_at=accepted_at)

    monkeypatch.setattr(
        finalizer_module,
        "NetworkRuntimeRepository",
        _FakeNetworkRuntimeRepository,
    )
    finalizer = NetworkRuntimeFinalizer(lambda: _FakeSession(execution))

    finalized = await finalizer.finalize(
        execution_id=execution.id,
        version=None,
        invocation_states=[],
        terminal_status="completed",
        output=None,
        trace_id=None,
    )

    assert finalized is True
    assert execution.started_at == accepted_at
