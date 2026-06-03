from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.metering.domain.repositories import UsageEventRepository
from modules.metering.infra.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUsageDailyProjectRepository,
    SQLAlchemyUsageEventRepository,
)
from modules.metering.service.use_cases import RecordUsageUseCase
from shared.domain.events import OutboxEventWriter


class MeteringProviders:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def record_usage_use_case(self) -> RecordUsageUseCase:
        repo: UsageEventRepository = SQLAlchemyUsageEventRepository(self.session)
        outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(self.session)
        return RecordUsageUseCase(repo, outbox)

    def get_project_daily_usage_use_case(self):
        repo = SQLAlchemyUsageDailyProjectRepository(self.session)
        return _GetProjectDailyUsageUseCase(repo)

    def get_agent_daily_usage_use_case(self):
        from modules.metering.infra.repositories import SQLAlchemyUsageDailyAgentRepository
        repo = SQLAlchemyUsageDailyAgentRepository(self.session)
        return _GetAgentDailyUsageUseCase(repo)


class _GetProjectDailyUsageUseCase:
    def __init__(self, repo):
        self._repo = repo

    async def execute(self, project_id: UUID, limit: int = 100, offset: int = 0):
        return await self._repo.list_by_project(project_id, limit, offset)


class _GetAgentDailyUsageUseCase:
    def __init__(self, repo):
        self._repo = repo

    async def execute(self, agent_id: UUID, limit: int = 100, offset: int = 0):
        return await self._repo.list_by_agent(agent_id, limit, offset)
