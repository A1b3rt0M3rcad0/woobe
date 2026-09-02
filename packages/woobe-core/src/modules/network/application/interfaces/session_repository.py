from abc import ABC, abstractmethod
from uuid import UUID

from modules.network.domain.entities import NetworkSession


class NetworkSessionRepository(ABC):
    @abstractmethod
    async def create(self, session: NetworkSession) -> NetworkSession: ...


class NetworkRuntimeEnvironmentRepository(ABC):
    @abstractmethod
    async def require_enabled(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> None: ...
