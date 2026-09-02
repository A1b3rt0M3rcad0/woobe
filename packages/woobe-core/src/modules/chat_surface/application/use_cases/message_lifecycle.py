from modules.chat_surface.application.dtos.message_request import (
    MarkMessageRequestInput,
    MessageRequestState,
)
from modules.chat_surface.application.interfaces.message_request_repository import (
    ChatSurfaceMessageRequestRepository,
)


class MarkChatSurfaceMessageUseCase:
    def __init__(self, repository: ChatSurfaceMessageRequestRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: MarkMessageRequestInput,
    ) -> MessageRequestState | None:
        return await self._repository.mark(input_dto)
