from __future__ import annotations

from typing import Protocol


class EmbeddingClient(Protocol):
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def aembed_query(self, text: str) -> list[float]: ...


class EmbeddingFactory(Protocol):
    def create_embedding_client(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        dimensions: int = 1536,
    ) -> EmbeddingClient: ...
