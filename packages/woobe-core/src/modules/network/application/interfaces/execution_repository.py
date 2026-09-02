from abc import ABC, abstractmethod
from uuid import UUID

from modules.network.application.dtos.execution import (
    AcceptedNetworkExecution,
    NetworkSessionAcceptanceState,
    NetworkVersionAcceptanceState,
    PersistNetworkExecutionInput,
)
from modules.network.domain.entities import Network


class NetworkExecutionAcceptanceRepository(ABC):
    @abstractmethod
    async def get_session(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        network_session_id: UUID,
        lock: bool,
    ) -> NetworkSessionAcceptanceState | None: ...

    @abstractmethod
    async def find_idempotent(
        self,
        *,
        network_id: UUID,
        idempotency_key: str,
    ) -> AcceptedNetworkExecution | None: ...

    @abstractmethod
    async def find_active(
        self,
        network_session_id: UUID,
    ) -> AcceptedNetworkExecution | None: ...

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
        network_id: UUID,
        project_id: UUID,
    ) -> NetworkVersionAcceptanceState | None: ...

    @abstractmethod
    async def persist_acceptance(
        self,
        input_dto: PersistNetworkExecutionInput,
    ) -> AcceptedNetworkExecution: ...
