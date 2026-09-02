from abc import ABC, abstractmethod
from uuid import UUID

from modules.network.application.dtos.rerun import (
    NetworkRerunExecutionState,
    NetworkRerunSessionState,
    NetworkRerunSource,
)


class NetworkRerunRepository(ABC):
    @abstractmethod
    async def get_source(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> NetworkRerunSource | None: ...

    @abstractmethod
    async def find_idempotent_execution(
        self,
        network_id: UUID,
        idempotency_key: str,
    ) -> NetworkRerunExecutionState | None: ...

    @abstractmethod
    async def find_active_execution_id(
        self,
        network_session_id: UUID,
    ) -> UUID | None: ...

    @abstractmethod
    async def get_session_state(
        self,
        network_session_id: UUID,
    ) -> NetworkRerunSessionState | None: ...

    @abstractmethod
    async def create_rerun(
        self,
        source: NetworkRerunSource,
        *,
        environment: str,
        idempotency_key: str | None,
    ) -> NetworkRerunExecutionState: ...
