from abc import ABC, abstractmethod
from uuid import UUID

from modules.network.domain.entities import Network


class NetworkResourceRepository(ABC):
    @abstractmethod
    async def list_by_project(self, project_id: UUID) -> list[Network]: ...

    @abstractmethod
    async def get_for_project(
        self,
        project_id: UUID,
        network_id: UUID,
    ) -> Network | None: ...

    @abstractmethod
    async def name_exists(
        self,
        project_id: UUID,
        name: str,
        *,
        exclude_network_id: UUID | None = None,
    ) -> bool: ...

    @abstractmethod
    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
    ) -> Network: ...

    @abstractmethod
    async def update_metadata(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        name: str | None,
        description: str | None,
    ) -> Network | None: ...
