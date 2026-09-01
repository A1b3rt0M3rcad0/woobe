from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class ToolExecutor(ABC):

    @abstractmethod
    async def execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        ...

    @abstractmethod
    async def tool_to_openai_definition(self, tool_id: UUID) -> dict | None:
        ...
