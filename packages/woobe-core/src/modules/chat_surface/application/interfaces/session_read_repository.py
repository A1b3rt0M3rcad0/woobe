from abc import ABC, abstractmethod
from uuid import UUID

from modules.chat_surface.application.dtos.session_read import (
    ChatSurfaceActivityState,
    ChatSurfaceSessionState,
)


class ChatSurfaceSessionReadRepository(ABC):
    @abstractmethod
    async def list_by_surface(
        self,
        surface_id: UUID,
        *,
        limit: int,
    ) -> list[ChatSurfaceSessionState]: ...

    @abstractmethod
    async def activity(self, surface_id: UUID) -> ChatSurfaceActivityState: ...
