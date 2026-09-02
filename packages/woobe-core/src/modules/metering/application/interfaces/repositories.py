from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from modules.metering.domain.entities import (
    UsageDailyAgent,
    UsageDailyProject,
    UsageEvent,
)
from shared.contracts.pagination import CursorPage


class UsageEventRepository(ABC):
    @abstractmethod
    async def save(self, event: UsageEvent) -> UsageEvent: ...

    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> UsageEvent | None: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageEvent]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UsageEvent]: ...

    @abstractmethod
    async def delete(self, event_id: UUID) -> None: ...


class UsageDailyProjectRepository(ABC):
    @abstractmethod
    async def save(self, daily: UsageDailyProject) -> UsageDailyProject: ...

    @abstractmethod
    async def get_by_project_and_day(
        self, project_id: UUID, day: str
    ) -> UsageDailyProject | None: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageDailyProject]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UsageDailyProject]: ...


class UsageDailyAgentRepository(ABC):
    @abstractmethod
    async def save(self, daily: UsageDailyAgent) -> UsageDailyAgent: ...

    @abstractmethod
    async def get_by_agent_and_day(
        self, agent_id: UUID, day: str
    ) -> UsageDailyAgent | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageDailyAgent]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UsageDailyAgent]: ...
