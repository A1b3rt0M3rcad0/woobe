from datetime import date
from typing import Any
from uuid import UUID

from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent


def __getattr__(name: str) -> Any: ...


class UsageEventRepository:
    async def save(self, event: UsageEvent) -> UsageEvent: ...


class UsageDailyProjectRepository:
    async def save(self, daily: UsageDailyProject) -> UsageDailyProject: ...
    async def get_by_project_and_day(
        self, project_id: UUID, day: date
    ) -> UsageDailyProject | None: ...


class UsageDailyAgentRepository:
    async def save(self, daily: UsageDailyAgent) -> UsageDailyAgent: ...
    async def get_by_agent_and_day(
        self, agent_id: UUID, day: date
    ) -> UsageDailyAgent | None: ...
