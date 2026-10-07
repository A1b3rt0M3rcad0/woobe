from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from langchain_openai import OpenAIEmbeddings


class EmbeddingProvider(Protocol):
    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        dimensions: int = 1536,
    ) -> Any: ...


class EmbeddingProviderRegistry:
    """Extensible provider registry for the current embedding client surface."""

    __slots__ = ("_providers", "_aliases")

    def __init__(self) -> None:
        self._providers: dict[str, EmbeddingProvider] = {}
        self._aliases: dict[str, str] = {}

    @staticmethod
    def _key(value: str) -> str:
        key = str(value).strip().lower()
        if not key:
            raise ValueError("Embedding provider key must not be empty")
        return key

    def register(self, key: str, provider: EmbeddingProvider) -> None:
        normalized = self._key(key)
        if normalized in self._providers or normalized in self._aliases:
            raise ValueError(f"Embedding provider already registered: {normalized}")
        self._providers[normalized] = provider

    def register_alias(self, alias: str, target: str) -> None:
        alias_key = self._key(alias)
        target_key = self._key(target)
        if alias_key in self._providers or alias_key in self._aliases:
            raise ValueError(f"Embedding provider already registered: {alias_key}")
        if target_key not in self._providers:
            raise ValueError(
                f"Embedding provider alias target is not registered: {target_key}"
            )
        self._aliases[alias_key] = target_key

    def resolve(self, key: str) -> EmbeddingProvider:
        normalized = self._key(key)
        canonical = self._aliases.get(normalized, normalized)
        provider = self._providers.get(canonical)
        if provider is None:
            raise ValueError(f"Embedding provider is not supported: {key}")
        return provider


@dataclass(frozen=True, slots=True)
class OpenAICompatibleEmbeddingProvider:
    default_base_url: str | None = None
    check_embedding_ctx_length: bool = True

    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        dimensions: int = 1536,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "check_embedding_ctx_length": self.check_embedding_ctx_length,
        }
        if dimensions:
            kwargs["dimensions"] = dimensions
        resolved_base_url = base_url or self.default_base_url
        if resolved_base_url:
            kwargs["base_url"] = resolved_base_url
        return OpenAIEmbeddings(**kwargs)


def build_embedding_provider_registry() -> EmbeddingProviderRegistry:
    registry = EmbeddingProviderRegistry()
    registry.register("openai", OpenAICompatibleEmbeddingProvider())
    registry.register(
        "openai_compatible",
        # Compatible servers own their tokenizer. Applying OpenAI's local
        # vocabulary to an arbitrary custom model changes its author input.
        OpenAICompatibleEmbeddingProvider(check_embedding_ctx_length=False),
    )
    registry.register(
        "openrouter",
        OpenAICompatibleEmbeddingProvider(
            default_base_url="https://openrouter.ai/api/v1",
            check_embedding_ctx_length=False,
        ),
    )
    registry.register_alias("custom", "openai_compatible")
    return registry


__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderRegistry",
    "OpenAICompatibleEmbeddingProvider",
    "build_embedding_provider_registry",
]
