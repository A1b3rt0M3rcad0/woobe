from abc import ABC, abstractmethod
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
