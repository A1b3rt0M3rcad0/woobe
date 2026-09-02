from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from modules.chat_surface.application.dtos.surface_mutation import CreateChatSurfaceInput
from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState


class ChatSurfaceMutationRepository(ABC):
    @abstractmethod
    async def create(
        self,
        input_dto: CreateChatSurfaceInput,
        *,
        public_id: str,
        normalized_name: str,
        allowed_origins: list[str],
    ) -> ChatSurfaceState: ...

    @abstractmethod
    async def get_for_update(self, surface_id: UUID) -> ChatSurfaceState | None: ...

    @abstractmethod
    async def update(
        self,
        surface_id: UUID,
        changes: dict[str, Any],
    ) -> ChatSurfaceState: ...

    @abstractmethod
    async def set_target_release(
        self,
        surface_id: UUID,
        target_release_id: UUID,
    ) -> ChatSurfaceState: ...

    @abstractmethod
    async def set_status(
        self,
        surface_id: UUID,
        *,
        status: str,
        token_epoch: int,
        activated_at: datetime | None,
        archived_at: datetime | None,
    ) -> ChatSurfaceState: ...


__all__ = ["ChatSurfaceMutationRepository"]
