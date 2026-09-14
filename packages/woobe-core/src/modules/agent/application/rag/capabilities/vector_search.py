from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class RAGVectorSearchCapability(Protocol):
    """Search the accepted vector snapshot behind a persistence boundary."""

    async def search(
        self,
        *,
        vector_snapshot_id: UUID,
        embedding: list[float],
        limit: int,
        threshold: float,
    ) -> list[tuple[Any, float]]: ...
