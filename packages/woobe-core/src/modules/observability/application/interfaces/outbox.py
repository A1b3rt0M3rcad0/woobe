from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class OutboxEventWriter(ABC):
    @abstractmethod
    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        routing_key: str,
        idempotency_key: str,
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None: ...
