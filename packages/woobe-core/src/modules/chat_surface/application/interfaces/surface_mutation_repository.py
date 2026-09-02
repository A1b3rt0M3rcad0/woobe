from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState


class ChatSurfaceMutationRepository(ABC):
    @abstractmethod
    async def get_for_update(self, surface_id: UUID) -> ChatSurfaceState | None: ...

    @abstractmethod
    async def update(
        self,
        surface_id: UUID,
        changes: dict[str, Any],
    ) -> ChatSurfaceState: ...

    @abstractmethod
    async def set_status(
        self,
        surface_id: UUID,
        *,
        status: str,
        token_epoch: int,
        archived_at: datetime | None,
    ) -> ChatSurfaceState: ...


__all__ = ["ChatSurfaceMutationRepository"]
