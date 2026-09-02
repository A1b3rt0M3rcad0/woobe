from abc import ABC, abstractmethod
from typing import Any, Protocol
from uuid import UUID

from modules.network.application.dtos.execution import NetworkExecutionControlState


class NetworkExecutionControlRepository(ABC):
    @abstractmethod
    async def get_execution(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> NetworkExecutionControlState | None: ...

    @abstractmethod
    async def request_durable_cancellation(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> NetworkExecutionControlState | None: ...


class NetworkExecutionRuntimeControl(Protocol):
    async def snapshot(self, execution_id: UUID) -> dict[str, Any]: ...

    async def request_cancel(self, execution_id: UUID) -> None: ...
