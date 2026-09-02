from abc import ABC, abstractmethod
from uuid import UUID

from modules.core.application.dtos.chat_surface_credential import (
    ChatSurfaceCredentialState,
)


class ChatSurfaceCredentialRepository(ABC):
    @abstractmethod
    async def get(
        self,
        credential_id: UUID,
    ) -> ChatSurfaceCredentialState | None: ...
