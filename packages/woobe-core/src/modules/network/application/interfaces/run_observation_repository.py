from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from modules.network.application.dtos.observation import NetworkRunObservation


class NetworkRunObservationRepository(ABC):
    @abstractmethod
    async def get(self, execution_id: UUID) -> NetworkRunObservation | None: ...

    @abstractmethod
    async def find_active(
        self,
        *,
        network_session_id: UUID | None = None,
        network_id: UUID | None = None,
        environment: str | None = None,
    ) -> NetworkRunObservation | None: ...

    @abstractmethod
    async def find_latest(
        self,
        *,
        network_session_id: UUID,
        network_id: UUID,
        project_id: UUID,
        network_version_id: UUID | None,
        created_after: datetime | None = None,
    ) -> NetworkRunObservation | None: ...
