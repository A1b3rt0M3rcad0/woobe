from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RAGEmbeddingCapability(Protocol):
    """Produce a query embedding without exposing provider/runtime details."""

    async def embed_query(self, text: str) -> list[float]: ...
