from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from modules.metering.application.use_cases import (
    GetAgentDailyUsageUseCase,
    GetProjectDailyUsageUseCase,
    RecordUsageUseCase,
)
from modules.metering.application.dtos import (
    DailyUsageResponse,
    RecordUsageInput,
)
from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent


class TestRecordUsageUseCase:
    @pytest.mark.anyio
    async def test_execute_records_usage(self):
        repo = AsyncMock()
        repo.save.return_value = UsageEvent(id=UUID("00000000-0000-0000-0000-000000000001"), project_id=UUID("00000000-0000-0000-0000-000000000002"))
        outbox = AsyncMock()
        use_case = RecordUsageUseCase(repo, outbox)

        result = await use_case.execute(RecordUsageInput(
            project_id=UUID("00000000-0000-0000-0000-000000000002"),
            event_type="llm_request",
            quantity=1.0,
            unit="request",
        ))

        assert result.event_id == UUID("00000000-0000-0000-0000-000000000001")
        repo.save.assert_awaited_once()
        outbox.write.assert_awaited_once()


class TestGetProjectDailyUsageUseCase:
    @pytest.mark.anyio
    async def test_execute_returns_daily_usage(self):
        from datetime import date

        repo = AsyncMock()
        repo.list_by_project.return_value = [
            UsageDailyProject(project_id=UUID("00000000-0000-0000-0000-000000000001"), day=date(2026, 6, 1), requests=100, cost_usd=0.05),
        ]
        use_case = GetProjectDailyUsageUseCase(repo)

        result = await use_case.execute(
            project_id=UUID("00000000-0000-0000-0000-000000000001"),
        )

        assert len(result) == 1
        assert isinstance(result[0], DailyUsageResponse)


class TestGetAgentDailyUsageUseCase:
    @pytest.mark.anyio
    async def test_execute_returns_daily_usage(self):
        from datetime import date

        repo = AsyncMock()
        repo.list_by_agent.return_value = [
            UsageDailyAgent(agent_id=UUID("00000000-0000-0000-0000-000000000001"), project_id=UUID("00000000-0000-0000-0000-000000000002"), day=date(2026, 6, 1), requests=50, cost_usd=0.02),
        ]
        use_case = GetAgentDailyUsageUseCase(repo)

        result = await use_case.execute(
            agent_id=UUID("00000000-0000-0000-0000-000000000001"),
        )

        assert len(result) == 1
        assert isinstance(result[0], DailyUsageResponse)
