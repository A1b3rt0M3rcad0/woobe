from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from modules.core.application.dtos.chat_surface_access_key import (
    ChatSurfaceAccessKeyAuthenticationCandidate,
    ChatSurfaceAccessKeyState,
    PersistChatSurfaceAccessKeyInput,
)


class ChatSurfaceAccessKeyRepository(ABC):
    @abstractmethod
    async def create(
        self,
        input_dto: PersistChatSurfaceAccessKeyInput,
    ) -> ChatSurfaceAccessKeyState: ...

    @abstractmethod
    async def list_by_surface(
        self,
        chat_surface_id: UUID,
    ) -> list[ChatSurfaceAccessKeyState]: ...

    @abstractmethod
    async def get_for_update(
        self,
        api_key_id: UUID,
    ) -> ChatSurfaceAccessKeyState | None: ...

    @abstractmethod
    async def find_authentication_candidates(
        self,
        *,
        chat_surface_id: UUID,
        key_prefix: str,
        key_version: int,
    ) -> list[ChatSurfaceAccessKeyAuthenticationCandidate]: ...

    @abstractmethod
    async def mark_used(
        self,
        api_key_id: UUID,
        *,
        used_at: datetime,
    ) -> ChatSurfaceAccessKeyState: ...

    @abstractmethod
    async def revoke(
        self,
        api_key_id: UUID,
        *,
        revoked_at: datetime,
    ) -> ChatSurfaceAccessKeyState: ...
