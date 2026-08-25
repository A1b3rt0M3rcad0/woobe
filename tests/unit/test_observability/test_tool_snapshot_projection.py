from uuid import uuid4

import pytest

from modules.observability.infra.messaging.trace_projector import (
    _save_tool_snapshot_if_missing,
)


class _FakeEventRepository:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.saved = []

    async def get_by_id(self, _event_id):
        return self.existing

    async def save(self, event):
        self.saved.append(event)
        return event


@pytest.mark.asyncio
async def test_completed_snapshot_does_not_overwrite_rich_tool_event() -> None:
    existing = object()
    repo = _FakeEventRepository(existing=existing)

    await _save_tool_snapshot_if_missing(
        repo,
        trace_id=uuid4(),
        project_id=uuid4(),
        discriminator="call-1",
        tool={
            "tool_call_id": "call-1",
            "tool_name": "search",
            "duration_ms": 100,
            # Completed snapshots intentionally do not carry operation timestamps.
        },
    )

    assert repo.saved == []


@pytest.mark.asyncio
async def test_completed_snapshot_is_used_only_when_tool_event_is_missing() -> None:
    repo = _FakeEventRepository(existing=None)
    trace_id = uuid4()

    await _save_tool_snapshot_if_missing(
        repo,
        trace_id=trace_id,
        project_id=uuid4(),
        discriminator="call-2",
        tool={
            "tool_call_id": "call-2",
            "tool_name": "search",
            "duration_ms": 100,
            "success": True,
        },
    )

    assert len(repo.saved) == 1
    event = repo.saved[0]
    assert event.payload["event"] == "agent.execution.tool_completed.v1"
    assert event.payload["tool_call_id"] == "call-2"
    assert event.trace_id == trace_id
