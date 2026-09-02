from modules.chat_surface.application.dtos.surface_read import (
    ChatSurfaceState,
    GetChatSurfaceInput,
    ListChatSurfacesInput,
)
from modules.chat_surface.application.interfaces.surface_read_repository import (
    ChatSurfaceReadRepository,
)
from shared.contracts.errors import NotFoundError


class ListChatSurfacesUseCase:
    def __init__(self, repository: ChatSurfaceReadRepository) -> None:
        self._repository = repository

    async def execute(self, input_dto: ListChatSurfacesInput) -> list[ChatSurfaceState]:
        return await self._repository.list_by_project(input_dto.project_id)


class GetChatSurfaceUseCase:
    def __init__(self, repository: ChatSurfaceReadRepository) -> None:
        self._repository = repository

    async def execute(self, input_dto: GetChatSurfaceInput) -> ChatSurfaceState:
        surface = await self._repository.get_by_id(input_dto.surface_id)
        if surface is None:
            raise NotFoundError("ChatSurface not found")
        return surface
