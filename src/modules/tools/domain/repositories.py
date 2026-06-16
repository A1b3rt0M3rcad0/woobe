from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from modules.tools.domain.entities import Secret, Tool
from shared.infra.objects import CursorPage


class ToolRepository(ABC):

    @abstractmethod
    async def create(self, tool: Tool) -> Tool: ...

    @abstractmethod
    async def get_by_id(self, tool_id: UUID) -> Tool: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Tool]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID, status: str | None = None
    ) -> list[Tool]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]: ...

    @abstractmethod
    async def update(self, tool: Tool) -> Tool: ...

    @abstractmethod
    async def delete(self, tool_id: UUID) -> None: ...


class SecretRepository(ABC):

    @abstractmethod
    async def create(self, secret: Secret) -> Secret: ...

    @abstractmethod
    async def get_by_id(self, secret_id: UUID) -> Secret: ...

    @abstractmethod
    async def get_by_name(self, project_id: UUID, name: str) -> Secret: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Secret]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Secret]: ...

    @abstractmethod
    async def update(self, secret: Secret) -> Secret: ...

    @abstractmethod
    async def delete(self, secret_id: UUID) -> None: ...

