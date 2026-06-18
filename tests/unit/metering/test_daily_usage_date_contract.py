from __future__ import annotations

import inspect
from datetime import date
from uuid import uuid4

import pytest

from modules.metering.infra.messaging import inbox_handlers
from modules.metering.infra.workers.inbox_processor import MeteringInboxProcessorWorker


@pytest.mark.asyncio
async def test_llm_handler_passes_date_objects_to_daily_repositories(monkeypatch) -> None:
    captured: dict[str, date] = {}

    class EventRepository:
        def __init__(self, session) -> None:
            pass

        async def save(self, event):
            return event

    class ProjectRepository:
        def __init__(self, session) -> None:
            pass

        async def get_by_project_and_day(self, project_id, day):
            captured["project_day"] = day
            return None

        async def save(self, daily):
            return daily

    class AgentRepository:
        def __init__(self, session) -> None:
            pass

        async def get_by_agent_and_day(self, agent_id, day):
            captured["agent_day"] = day
            return None

        async def save(self, daily):
            return daily

    monkeypatch.setattr(inbox_handlers, "SQLAlchemyUsageEventRepository", EventRepository)
    monkeypatch.setattr(
        inbox_handlers,
        "SQLAlchemyUsageDailyProjectRepository",
        ProjectRepository,
    )
    monkeypatch.setattr(
        inbox_handlers,
        "SQLAlchemyUsageDailyAgentRepository",
        AgentRepository,
    )

    await inbox_handlers.handle_llm_request(
        event_type="agent.execution.llm_completed.v1",
        payload={
            "project_id": str(uuid4()),
            "agent_id": str(uuid4()),
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.01,
        },
        session=object(),
    )

    assert isinstance(captured["project_day"], date)
    assert isinstance(captured["agent_day"], date)


def test_metering_processor_uses_separate_failure_transaction() -> None:
    source = inspect.getsource(MeteringInboxProcessorWorker)

    assert "await self._process_record(record)" in source
    assert "await self._persist_failure(record, str(exc))" in source
    assert source.count("async with AsyncSession(self._async_engine) as session") >= 3
