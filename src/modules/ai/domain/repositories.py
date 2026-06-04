from abc import ABC, abstractmethod
from uuid import UUID

from modules.ai.domain.entities import Agent, ProviderCredential
from shared.domain.objects import CursorPage


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
    ) -> list[ProviderCredential]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[ProviderCredential]: ...

    @abstractmethod
    async def update(
        self, credential: ProviderCredential
    ) -> ProviderCredential: ...

    @abstractmethod
    async def delete(self, credential_id: UUID) -> None: ...


class AgentRepository(ABC):

    @abstractmethod
    async def save(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def get_by_id(self, agent_id: UUID) -> Agent | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Agent]: ...  # TODO: Remove after pagination migration

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Agent]: ...

    @abstractmethod
    async def update(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def delete(self, agent_id: UUID) -> None: ...
