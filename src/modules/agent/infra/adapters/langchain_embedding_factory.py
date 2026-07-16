from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from modules.agent.domain.ports.embedding_factory import EmbeddingFactory

_OPENAI_COMPATIBLE_PROVIDERS = {"openai", "custom", "openrouter"}


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
        return OpenAIEmbeddings(**kwargs)
