from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from langchain_openai import ChatOpenAI

from modules.agent.infra.llm.anthropic_chat_model import AnthropicChatModel


class LegacyChatProvider(Protocol):
    """Provider-specific construction for the compatibility chat-model surface."""

    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        streaming: bool = False,
        response_format: dict | None = None,
    ) -> Any: ...


class LegacyChatProviderRegistry:
    """Extensible registry used only by the legacy LLMFactory compatibility path."""

    __slots__ = ("_providers", "_aliases")

    def __init__(self) -> None:
        self._providers: dict[str, LegacyChatProvider] = {}
        self._aliases: dict[str, str] = {}

    @staticmethod
    def _key(value: str) -> str:
        key = str(value).strip().lower()
        if not key:
            raise ValueError("Legacy chat provider key must not be empty")
        return key

    def register(self, key: str, provider: LegacyChatProvider) -> None:
        normalized = self._key(key)
        if normalized in self._providers or normalized in self._aliases:
            raise ValueError(f"Legacy chat provider already registered: {normalized}")
        self._providers[normalized] = provider

    def register_alias(self, alias: str, target: str) -> None:
        alias_key = self._key(alias)
        target_key = self._key(target)
        if alias_key in self._providers or alias_key in self._aliases:
            raise ValueError(f"Legacy chat provider already registered: {alias_key}")
        if target_key not in self._providers:
            raise ValueError(
                f"Legacy chat provider alias target is not registered: {target_key}"
            )
        self._aliases[alias_key] = target_key

    def resolve(self, key: str) -> LegacyChatProvider:
        normalized = self._key(key)
        canonical = self._aliases.get(normalized, normalized)
        provider = self._providers.get(canonical)
        if provider is None:
            raise ValueError(f"Unsupported provider: {key}")
        return provider

    def keys(self) -> frozenset[str]:
        return frozenset((*self._providers.keys(), *self._aliases.keys()))


@dataclass(frozen=True, slots=True)
class OpenAICompatibleChatProvider:
    default_base_url: str | None = None

    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        streaming: bool = False,
        response_format: dict | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resolved_base_url = base_url or self.default_base_url
        if streaming:
            kwargs["streaming"] = True
            kwargs["stream_usage"] = True
        if resolved_base_url:
            kwargs["base_url"] = resolved_base_url
        if response_format:
            kwargs["response_format"] = response_format
        return ChatOpenAI(**kwargs)


@dataclass(frozen=True, slots=True)
class AnthropicChatProvider:
    default_base_url: str | None = None

    def create(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        streaming: bool = False,
        response_format: dict | None = None,
    ) -> Any:
        # AnthropicChatModel exposes the same Woobe compatibility surface. Native
        # provider streaming can evolve behind this provider implementation.
        return AnthropicChatModel(
            model=model,
            api_key=api_key,
            base_url=base_url or self.default_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )


def build_legacy_chat_provider_registry() -> LegacyChatProviderRegistry:
    registry = LegacyChatProviderRegistry()

    registry.register("openai", OpenAICompatibleChatProvider())
    registry.register(
        "openai_compatible",
        OpenAICompatibleChatProvider(),
    )
    registry.register(
        "openrouter",
        OpenAICompatibleChatProvider(
            default_base_url="https://openrouter.ai/api/v1",
        ),
    )
    registry.register(
        "deepseek",
        OpenAICompatibleChatProvider(
            default_base_url="https://api.deepseek.com",
        ),
    )
    registry.register("anthropic", AnthropicChatProvider())

    # Existing persisted custom credentials remain OpenAI-compatible.
    registry.register_alias("custom", "openai_compatible")
    return registry


__all__ = [
    "AnthropicChatProvider",
    "LegacyChatProvider",
    "LegacyChatProviderRegistry",
    "OpenAICompatibleChatProvider",
    "build_legacy_chat_provider_registry",
]
