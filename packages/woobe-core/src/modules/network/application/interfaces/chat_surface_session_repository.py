from abc import ABC, abstractmethod

from modules.network.application.dtos.chat_surface_session import (
    CloseNetworkChatSurfaceSessionInput,
    CreateNetworkChatSurfaceSessionInput,
    NetworkChatSurfaceSessionState,
)


class NetworkChatSurfaceSessionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        input_dto: CreateNetworkChatSurfaceSessionInput,
    ) -> NetworkChatSurfaceSessionState: ...

    @abstractmethod
    async def close(
        self,
        input_dto: CloseNetworkChatSurfaceSessionInput,
    ) -> NetworkChatSurfaceSessionState: ...
