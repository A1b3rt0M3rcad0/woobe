from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class ToolRepository(ABC):

    @abstractmethod
    async def list_by_agent(self, agent_id: UUID, status: str | None = None) -> list:
        ...

    @abstractmethod
    async def get_by_id(self, tool_id: UUID):
        ...
