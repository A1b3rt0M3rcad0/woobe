from abc import ABC, abstractmethod
from uuid import UUID

from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState


class ChatSurfaceReadRepository(ABC):
    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[ChatSurfaceState]: ...

    @abstractmethod
    async def get_by_id(self, surface_id: UUID) -> ChatSurfaceState | None: ...

    @abstractmethod
    async def get_by_public_id(self, public_id: str) -> ChatSurfaceState | None: ...
