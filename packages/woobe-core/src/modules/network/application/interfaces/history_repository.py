from abc import ABC, abstractmethod
from uuid import UUID

from modules.network.application.dtos.history import (
    NetworkExecutionEventOutput,
    NetworkMessageHistoryOutput,
    NetworkSessionHistoryOutput,
)


class NetworkHistoryRepository(ABC):
    @abstractmethod
    async def list_sessions(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        limit: int = 100,
    ) -> list[NetworkSessionHistoryOutput]: ...

    @abstractmethod
    async def session_exists(
        self,
        *,
        network_id: UUID,
        network_session_id: UUID,
        project_id: UUID,
    ) -> bool: ...

    @abstractmethod
    async def list_messages(
        self,
        *,
        network_session_id: UUID,
        project_id: UUID,
        offset: int,
        limit: int,
    ) -> list[NetworkMessageHistoryOutput]: ...

    @abstractmethod
    async def has_active_execution(self, network_session_id: UUID) -> bool: ...

    @abstractmethod
    async def clear_agent_contexts(self, network_session_id: UUID) -> None: ...

    @abstractmethod
    async def execution_exists(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> bool: ...

    @abstractmethod
    async def list_execution_events(
        self,
        *,
        execution_id: UUID,
        after_sequence: int,
        limit: int,
    ) -> list[NetworkExecutionEventOutput]: ...
