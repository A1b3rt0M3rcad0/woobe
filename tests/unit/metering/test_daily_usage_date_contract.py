from __future__ import annotations

import inspect
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from modules.metering.infra.messaging import inbox_handlers
from woobe_workers.consumers.metering.inbox_processor import MeteringInboxProcessorWorker


@pytest.mark.asyncio
async def test_llm_handler_passes_event_day_to_atomic_projection(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class EventRepository:
        def __init__(self, session) -> None:
            pass

        async def save(self, event):
            captured["event"] = event
            return event

    async def capture_increment(session, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(inbox_handlers, "SQLAlchemyUsageEventRepository", EventRepository)
    monkeypatch.setattr(inbox_handlers, "_increment_daily", capture_increment)

    occurred_at = datetime(2026, 7, 13, 23, 59, tzinfo=UTC)
    await inbox_handlers.handle_llm_request(
        event_type="agent.execution.llm_completed.v1",
        payload={
            "project_id": str(uuid4()),
            "agent_id": str(uuid4()),
            "trace_id": str(uuid4()),
            "occurred_at": occurred_at.isoformat(),
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.01,
            "cost_status": "known",
        },
        session=object(),
        source_event_id=uuid4(),
    )

    assert isinstance(captured["day"], date)
    assert captured["day"] == occurred_at.date()
    assert captured["occurred_at"] == occurred_at


def test_metering_processor_uses_separate_failure_transaction() -> None:
    source = inspect.getsource(MeteringInboxProcessorWorker)

    assert "await self._process_record(record)" in source
    assert "await self._persist_failure(record, str(exc))" in source
    assert source.count("async with AsyncSession(self._async_engine) as session") >= 3
