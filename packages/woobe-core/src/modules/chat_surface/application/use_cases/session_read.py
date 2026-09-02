from modules.chat_surface.application.dtos.session_read import (
    ChatSurfaceActivityState,
    ChatSurfaceSessionState,
    GetChatSurfaceActivityInput,
    ListChatSurfaceSessionsInput,
)
from modules.chat_surface.application.interfaces.session_read_repository import (
    ChatSurfaceSessionReadRepository,
)


class ListChatSurfaceSessionsUseCase:
    def __init__(self, repository: ChatSurfaceSessionReadRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ListChatSurfaceSessionsInput,
    ) -> list[ChatSurfaceSessionState]:
        safe_limit = min(100, max(1, input_dto.limit))
        return await self._repository.list_by_surface(
            input_dto.surface_id,
            limit=safe_limit,
        )


class GetChatSurfaceActivityUseCase:
    def __init__(self, repository: ChatSurfaceSessionReadRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: GetChatSurfaceActivityInput,
    ) -> ChatSurfaceActivityState:
        return await self._repository.activity(input_dto.surface_id)
