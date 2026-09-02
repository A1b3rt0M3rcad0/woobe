from abc import ABC, abstractmethod

from modules.agent.application.dtos.chat_surface_session import (
    AgentChatSurfaceSessionState,
    CloseAgentChatSurfaceSessionInput,
    CreateAgentChatSurfaceSessionInput,
)


class AgentChatSurfaceSessionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        input_dto: CreateAgentChatSurfaceSessionInput,
    ) -> AgentChatSurfaceSessionState: ...

    @abstractmethod
    async def close(
        self,
        input_dto: CloseAgentChatSurfaceSessionInput,
    ) -> AgentChatSurfaceSessionState: ...
