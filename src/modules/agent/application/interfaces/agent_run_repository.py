from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from modules.agent.domain.run import AgentRun


class AgentRunRepository(ABC):
    @abstractmethod
    async def create(self, run: AgentRun) -> AgentRun: ...

    @abstractmethod
    async def get_by_id(self, run_id: UUID) -> AgentRun | None: ...

    @abstractmethod
    async def get_active_direct_by_session(
        self,
        session_id: UUID,
    ) -> AgentRun | None: ...

    @abstractmethod
    async def save(self, run: AgentRun) -> AgentRun: ...
