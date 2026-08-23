from abc import ABC, abstractmethod
from uuid import UUID

from modules.agent.domain.release_activation import AgentReleaseActivation


class AgentReleaseActivationRepository(ABC):
    @abstractmethod
    async def save(
        self,
        activation: AgentReleaseActivation,
    ) -> AgentReleaseActivation: ...

    @abstractmethod
    async def list_by_agent(
        self,
        agent_id: UUID,
    ) -> list[AgentReleaseActivation]: ...
