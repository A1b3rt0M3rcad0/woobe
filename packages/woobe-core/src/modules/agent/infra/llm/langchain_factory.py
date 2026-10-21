from __future__ import annotations

from typing import Any

from modules.agent.infra.llm.providers import (
    LegacyChatProviderRegistry,
    build_legacy_chat_provider_registry,
)


_DEFAULT_PROVIDER_REGISTRY = build_legacy_chat_provider_registry()


def create_chat_model(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    streaming: bool = False,
    response_format: dict | None = None,
    max_retries: int | None = None,
    *,
    registry: LegacyChatProviderRegistry | None = None,
) -> Any:
    provider_registry = registry or _DEFAULT_PROVIDER_REGISTRY
    implementation = provider_registry.resolve(provider)
    options = dict(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        response_format=response_format,
    )
    if max_retries is not None:
        if type(max_retries) is not int or not 0 <= max_retries <= 10:
            raise ValueError("Model retry limit must be a bounded non-negative integer")
        options["max_retries"] = max_retries
    return implementation.create(**options)
