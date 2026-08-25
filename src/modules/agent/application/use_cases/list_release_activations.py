from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.release_activation_repository import (
    AgentReleaseActivationRepository,
)
from modules.agent.domain.release_activation import AgentReleaseActivation


class ListAgentReleaseActivationsUseCase:
    def __init__(self, activation_repo: AgentReleaseActivationRepository) -> None:
        self._activation_repo = activation_repo

    async def execute(self, agent_id: UUID) -> list[AgentReleaseActivation]:
        return await self._activation_repo.list_by_agent(agent_id)
