from sqlalchemy.ext.asyncio import AsyncSession

from modules.metering.infra.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUsageDailyAgentRepository,
    SQLAlchemyUsageDailyProjectRepository,
    SQLAlchemyUsageEventRepository,
)
from modules.metering.service.use_cases import (
    GetAgentDailyUsageUseCase,
    GetProjectDailyUsageUseCase,
    RecordUsageUseCase,
)


class MeteringProviders:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def record_usage_use_case(self) -> RecordUsageUseCase:
        return RecordUsageUseCase(
            repo=SQLAlchemyUsageEventRepository(self._session),
            outbox=SQLAlchemyOutboxEventWriter(self._session),
        )

    def get_project_daily_usage_use_case(self) -> GetProjectDailyUsageUseCase:
        return GetProjectDailyUsageUseCase(
            repo=SQLAlchemyUsageDailyProjectRepository(self._session),
        )

    def get_agent_daily_usage_use_case(self) -> GetAgentDailyUsageUseCase:
        return GetAgentDailyUsageUseCase(
            repo=SQLAlchemyUsageDailyAgentRepository(self._session),
        )
