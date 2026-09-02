from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from modules.network.application.dtos.management import (
    ManagedNetworkVersion,
    NetworkProductionActivation,
    NetworkProductionState,
)


class NetworkManagementRepository(ABC):
    @abstractmethod
    async def list_versions(
        self,
        network_id: UUID,
        project_id: UUID,
    ) -> list[ManagedNetworkVersion]: ...

    @abstractmethod
    async def list_activations(
        self,
        network_id: UUID,
        project_id: UUID,
    ) -> list[NetworkProductionActivation]: ...

    @abstractmethod
    async def get_execution_snapshot(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    async def get_production_state(
        self,
        network_id: UUID,
        project_id: UUID,
        *,
        lock: bool,
    ) -> NetworkProductionState | None: ...

    @abstractmethod
    async def get_version(
        self,
        version_id: UUID,
        project_id: UUID,
    ) -> ManagedNetworkVersion | None: ...

    @abstractmethod
    async def activate_production(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        version_id: UUID,
        previous_version_id: UUID | None,
        activation_kind: str,
        change_description: str,
        created_by: UUID | None,
    ) -> NetworkProductionActivation: ...
