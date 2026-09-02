from abc import ABC, abstractmethod
from uuid import UUID

from modules.chat_surface.application.dtos.public_session import (
    ChatSurfaceSessionBindingState,
    CreateChatSurfaceSessionBindingInput,
)
from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState


class ChatSurfacePublicSessionRepository(ABC):
    @abstractmethod
    async def get_surface(
        self,
        surface_id: UUID,
        *,
        for_update: bool = False,
    ) -> ChatSurfaceState | None: ...

    @abstractmethod
    async def get_by_idempotency(
        self,
        surface_id: UUID,
        idempotency_key: str,
    ) -> ChatSurfaceSessionBindingState | None: ...

    @abstractmethod
    async def get_binding(
        self,
        surface_id: UUID,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> ChatSurfaceSessionBindingState | None: ...

    @abstractmethod
    async def create_binding(
        self,
        input_dto: CreateChatSurfaceSessionBindingInput,
        *,
        idempotency_key: str,
    ) -> ChatSurfaceSessionBindingState: ...

    @abstractmethod
    async def archive_binding(
        self,
        surface_id: UUID,
        session_id: UUID,
    ) -> ChatSurfaceSessionBindingState: ...
