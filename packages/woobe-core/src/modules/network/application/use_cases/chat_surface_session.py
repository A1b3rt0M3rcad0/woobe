from modules.network.application.dtos.chat_surface_session import (
    CloseNetworkChatSurfaceSessionInput,
    CreateNetworkChatSurfaceSessionInput,
    NetworkChatSurfaceSessionState,
)
from modules.network.application.interfaces.chat_surface_session_repository import (
    NetworkChatSurfaceSessionRepository,
)


class CreateNetworkChatSurfaceSessionUseCase:
    def __init__(self, repository: NetworkChatSurfaceSessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: CreateNetworkChatSurfaceSessionInput,
    ) -> NetworkChatSurfaceSessionState:
        return await self._repository.create(input_dto)


class CloseNetworkChatSurfaceSessionUseCase:
    def __init__(self, repository: NetworkChatSurfaceSessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: CloseNetworkChatSurfaceSessionInput,
    ) -> NetworkChatSurfaceSessionState:
        return await self._repository.close(input_dto)


__all__ = [
    "CloseNetworkChatSurfaceSessionUseCase",
    "CreateNetworkChatSurfaceSessionUseCase",
]
