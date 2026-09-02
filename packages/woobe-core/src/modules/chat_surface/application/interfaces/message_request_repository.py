from abc import ABC, abstractmethod
from uuid import UUID

from modules.chat_surface.application.dtos.message_request import (
    MarkMessageRequestInput,
    MessageRequestState,
)


class ChatSurfaceMessageRequestRepository(ABC):
    @abstractmethod
    async def get(self, request_id: UUID) -> MessageRequestState | None: ...

    @abstractmethod
    async def mark(
        self,
        input_dto: MarkMessageRequestInput,
    ) -> MessageRequestState | None: ...
