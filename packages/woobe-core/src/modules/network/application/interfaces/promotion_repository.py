from abc import ABC, abstractmethod
from uuid import UUID

from modules.network.application.dtos.management import ManagedNetworkVersion
from modules.network.application.dtos.promotion import CreateNetworkPromotionVersionInput
from modules.network.domain.entities import Network


class NetworkPromotionRepository(ABC):
    @abstractmethod
    async def get_network(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        lock: bool,
    ) -> Network | None: ...

    @abstractmethod
    async def get_version(
        self,
        *,
        version_id: UUID,
        project_id: UUID,
        network_id: UUID,
        lock: bool,
    ) -> ManagedNetworkVersion | None: ...

    @abstractmethod
    async def list_version_names(self, network_id: UUID, kind: str) -> list[str]: ...

    @abstractmethod
    async def find_by_fingerprint(
        self,
        *,
        network_id: UUID,
        kind: str,
        fingerprint: str,
    ) -> ManagedNetworkVersion | None: ...

    @abstractmethod
    async def create_version(
        self,
        input_dto: CreateNetworkPromotionVersionInput,
    ) -> ManagedNetworkVersion: ...

    @abstractmethod
    async def set_staging_version(self, network_id: UUID, version_id: UUID) -> None: ...

    @abstractmethod
    async def set_production_version(self, network_id: UUID, version_id: UUID) -> None: ...

    @abstractmethod
    async def record_activation(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        version_id: UUID,
        previous_version_id: UUID | None,
        activation_kind: str,
        change_description: str,
        created_by: UUID | None,
    ) -> None: ...
