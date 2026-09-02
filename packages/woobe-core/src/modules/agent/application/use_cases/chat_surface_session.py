from modules.agent.application.dtos.chat_surface_session import (
    AgentChatSurfaceSessionState,
    CloseAgentChatSurfaceSessionInput,
    CreateAgentChatSurfaceSessionInput,
)
from modules.agent.application.interfaces.chat_surface_session_repository import (
    AgentChatSurfaceSessionRepository,
)


class CreateAgentChatSurfaceSessionUseCase:
    def __init__(self, repository: AgentChatSurfaceSessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: CreateAgentChatSurfaceSessionInput,
    ) -> AgentChatSurfaceSessionState:
        return await self._repository.create(input_dto)


class CloseAgentChatSurfaceSessionUseCase:
    def __init__(self, repository: AgentChatSurfaceSessionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: CloseAgentChatSurfaceSessionInput,
    ) -> AgentChatSurfaceSessionState:
        return await self._repository.close(input_dto)


__all__ = [
    "CloseAgentChatSurfaceSessionUseCase",
    "CreateAgentChatSurfaceSessionUseCase",
]
