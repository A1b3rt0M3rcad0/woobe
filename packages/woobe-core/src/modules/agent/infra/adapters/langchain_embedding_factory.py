from __future__ import annotations

from typing import Any

from modules.agent.application.interfaces.embedding_errors import (
    as_embedding_provider_error,
)
from modules.agent.application.interfaces.embedding_factory import EmbeddingFactory
from modules.agent.infra.models.embedding_providers import (
    EmbeddingProviderRegistry,
    build_embedding_provider_registry,
)


class _SafeEmbeddingClient:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate

    async def aembed_documents(self, texts: list[str]):
        try:
            return await self._delegate.aembed_documents(texts)
        except Exception as exc:
            raise as_embedding_provider_error(exc) from exc

    async def aembed_query(self, text: str):
        try:
            return await self._delegate.aembed_query(text)
        except Exception as exc:
            raise as_embedding_provider_error(exc) from exc

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


class LangchainEmbeddingFactory(EmbeddingFactory):
    def __init__(
        self,
        provider_registry: EmbeddingProviderRegistry | None = None,
    ) -> None:
        self._provider_registry = (
            provider_registry or build_embedding_provider_registry()
        )

    def create_embedding_client(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        dimensions: int = 1536,
    ):
        try:
            implementation = self._provider_registry.resolve(provider)
            return _SafeEmbeddingClient(
                implementation.create(
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    dimensions=dimensions,
                )
            )
        except Exception as exc:
            raise as_embedding_provider_error(exc) from exc
