from __future__ import annotations

from typing import Any

from langchain_openai import OpenAIEmbeddings

from modules.agent.application.interfaces.embedding_errors import (
    as_embedding_provider_error,
)
from modules.agent.application.interfaces.embedding_factory import EmbeddingFactory

_OPENAI_COMPATIBLE_PROVIDERS = {"openai", "custom", "openrouter"}


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
            if provider not in _OPENAI_COMPATIBLE_PROVIDERS:
                raise ValueError(f"Embedding provider is not supported for MVP: {provider}")

            resolved_base_url = base_url
            if provider == "openrouter" and not resolved_base_url:
                resolved_base_url = "https://openrouter.ai/api/v1"

            kwargs: dict = {"model": model, "api_key": api_key}
            if dimensions:
                kwargs["dimensions"] = dimensions
            if resolved_base_url:
                kwargs["base_url"] = resolved_base_url
            return _SafeEmbeddingClient(OpenAIEmbeddings(**kwargs))
        except Exception as exc:
            raise as_embedding_provider_error(exc) from exc
