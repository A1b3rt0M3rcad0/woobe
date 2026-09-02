from datetime import date
from uuid import UUID

import pytest

from modules.metering.application.dtos import (
    DailyUsageResponse,
    RecordUsageInput,
    RecordUsageOutput,
)
from modules.metering.application.interfaces.outbox import OutboxEventWriter
from modules.metering.application.interfaces.repositories import (
    UsageDailyAgentRepository,
    UsageDailyProjectRepository,
    UsageEventRepository,
)
from modules.metering.application.use_cases import (
    GetAgentDailyUsageUseCase,
    GetProjectDailyUsageUseCase,
    RecordUsageUseCase,
)
from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject
from tests.helpers import fake_uuid, make_usage_event


class TestRecordUsageUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=UsageEventRepository)
        saved = make_usage_event()
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = RecordUsageInput(
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            event_type=saved.event_type,
            quantity=saved.quantity,
            unit=saved.unit,
        )

        uc = RecordUsageUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert isinstance(result, RecordUsageOutput)
        assert result.event_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_cost_and_metadata(self, mocker):
        mock_repo = mocker.AsyncMock(spec=UsageEventRepository)
        saved = make_usage_event()
        saved.cost_usd = 0.05
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = RecordUsageInput(
            project_id=saved.project_id,
            event_type=saved.event_type,
            quantity=saved.quantity,
            unit=saved.unit,
            cost_usd=0.05,
        )

        uc = RecordUsageUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert result.event_id == saved.id
        mock_repo.save.assert_awaited_once()


class TestGetProjectDailyUsageUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=UsageDailyProjectRepository)
        items = [
            UsageDailyProject(
                project_id=UUID(fake_uuid()),
                day=date(2026, 6, 1),
                requests=100,
                input_tokens=5000,
                output_tokens=10000,
                cost_usd=0.25,
            )
        ]
        mock_repo.list_by_project.return_value = items

        uc = GetProjectDailyUsageUseCase(repo=mock_repo)
        result = await uc.execute(project_id=UUID(fake_uuid()))

        assert len(result) == 1
        assert isinstance(result[0], DailyUsageResponse)
        assert result[0].requests == 100
        assert result[0].cost_usd == 0.25
        mock_repo.list_by_project.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty(self, mocker):
        mock_repo = mocker.AsyncMock(spec=UsageDailyProjectRepository)
        mock_repo.list_by_project.return_value = []

        uc = GetProjectDailyUsageUseCase(repo=mock_repo)
        result = await uc.execute(project_id=UUID(fake_uuid()))

        assert result == []
        mock_repo.list_by_project.assert_awaited_once()


class TestGetAgentDailyUsageUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=UsageDailyAgentRepository)
        items = [
            UsageDailyAgent(
                agent_id=UUID(fake_uuid()),
                project_id=UUID(fake_uuid()),
                day=date(2026, 6, 1),
                requests=50,
                input_tokens=2500,
                cost_usd=0.12,
            )
        ]
        mock_repo.list_by_agent.return_value = items

        uc = GetAgentDailyUsageUseCase(repo=mock_repo)
        result = await uc.execute(agent_id=UUID(fake_uuid()))

        assert len(result) == 1
        assert isinstance(result[0], DailyUsageResponse)
        assert result[0].requests == 50
        mock_repo.list_by_agent.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty(self, mocker):
        mock_repo = mocker.AsyncMock(spec=UsageDailyAgentRepository)
        mock_repo.list_by_agent.return_value = []

        uc = GetAgentDailyUsageUseCase(repo=mock_repo)
        result = await uc.execute(agent_id=UUID(fake_uuid()))

        assert result == []
        mock_repo.list_by_agent.assert_awaited_once()
