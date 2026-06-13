from abc import ABC, abstractmethod
from uuid import UUID

from modules.agent.domain.entities import (
    Agent,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    ProviderCredential,
)
from modules.agent.domain.enums import ReleaseStatus
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
    ) -> list[ProviderCredential]: ...

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
    async def list_by_project(self, project_id: UUID) -> list[Agent]: ...

    @abstractmethod
    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Agent]: ...

    @abstractmethod
    async def update(self, agent: Agent) -> Agent: ...

    @abstractmethod
    async def delete(self, agent_id: UUID) -> None: ...


class AgentPromptRepository(ABC):

    @abstractmethod
    async def save(self, prompt: AgentPrompt) -> AgentPrompt: ...

    @abstractmethod
    async def get_by_id(self, prompt_id: UUID) -> AgentPrompt | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentPrompt | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentPrompt]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentPrompt]: ...


class AgentContractRepository(ABC):

    @abstractmethod
    async def save(self, contract: AgentContract) -> AgentContract: ...

    @abstractmethod
    async def get_by_id(self, contract_id: UUID) -> AgentContract | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentContract | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentContract]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentContract]: ...

    @abstractmethod
    async def delete(self, contract_id: UUID) -> None: ...


class AgentModelConfigRepository(ABC):

    @abstractmethod
    async def save(self, config: AgentModelConfig) -> AgentModelConfig: ...

    @abstractmethod
    async def get_by_id(self, config_id: UUID) -> AgentModelConfig | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentModelConfig | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentModelConfig]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentModelConfig]: ...


class AgentReleaseRepository(ABC):

    @abstractmethod
    async def save(self, release: AgentRelease) -> AgentRelease: ...

    @abstractmethod
    async def get_by_id(self, release_id: UUID) -> AgentRelease | None: ...

    @abstractmethod
    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentRelease | None: ...

    @abstractmethod
    async def get_active_production(
        self, agent_id: UUID
    ) -> AgentRelease | None: ...

    @abstractmethod
    async def list_by_agent(
        self, agent_id: UUID
    ) -> list[AgentRelease]: ...

    @abstractmethod
    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentRelease]: ...

    @abstractmethod
    async def list_by_status(
        self, agent_id: UUID, status: ReleaseStatus
    ) -> list[AgentRelease]: ...

    @abstractmethod
    async def get_last_promoted(
        self, agent_id: UUID, *, exclude_id: UUID
    ) -> AgentRelease | None: ...

    @abstractmethod
    async def delete(self, release_id: UUID) -> None: ...


class AgentReleaseTestRepository(ABC):

    @abstractmethod
    async def save(self, test: AgentReleaseTest) -> AgentReleaseTest: ...

    @abstractmethod
    async def get_by_id(self, test_id: UUID) -> AgentReleaseTest | None: ...

    @abstractmethod
    async def list_by_release(
        self, release_id: UUID
    ) -> list[AgentReleaseTest]: ...

    @abstractmethod
    async def paginate_by_release(
        self, release_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentReleaseTest]: ...
