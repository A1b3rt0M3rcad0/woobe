from abc import ABC, abstractmethod
from uuid import UUID

from modules.ai.domain.entities import Agent, ProviderCredential


class ProviderCredentialRepository(ABC):

    @abstractmethod
    async def save(
        self, credential: ProviderCredential
    ) -> ProviderCredential: ...

    @abstractmethod
    async def get_by_id(self, credential_id: UUID) -> ProviderCredential | None: ...

    @abstractmethod
    async def list_by_project(
        self, project_id: UUID
    ) -> list[ProviderCredential]: ...

    @abstractmethod
    async def delete(self, credential_id: UUID) -> None: ...


class AgentRepository(ABC):

    @abstractmethod
    async def save(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Agent | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Agent]: ...

    @abstractmethod
    async def delete(self, agent_id: UUID) -> None: ...
