from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI


def create_chat_model(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
) -> BaseChatModel:
    if provider in ("openai", "custom"):
        kwargs: dict = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if base_url:
            kwargs["base_url"] = base_url
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
