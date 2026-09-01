from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI


_OPENAI_COMPATIBLE_PROVIDERS = {"openai", "custom", "openrouter"}


def create_chat_model(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    streaming: bool = False,
    response_format: dict | None = None,
) -> BaseChatModel:
    if provider in _OPENAI_COMPATIBLE_PROVIDERS:
        kwargs: dict = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resolved_base_url = base_url
        if provider == "openrouter" and not resolved_base_url:
            resolved_base_url = "https://openrouter.ai/api/v1"
        if streaming:
            kwargs["streaming"] = True
            kwargs["stream_usage"] = True
        if resolved_base_url:
            kwargs["base_url"] = resolved_base_url
        if response_format:
            kwargs["response_format"] = response_format
        return ChatOpenAI(**kwargs)

    if provider == "anthropic":
        raise NotImplementedError(
            "Provider anthropic is not implemented yet. "
            "Install langchain-anthropic and add support."
        )

    if provider == "google":
        raise NotImplementedError(
            "Provider google is not implemented yet. "
            "Install langchain-google-genai and add support."
        )

    raise ValueError(f"Unsupported provider: {provider}")
