from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI

from modules.agent.infra.llm.anthropic_chat_model import AnthropicChatModel


_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "custom",
    "openai_compatible",
    "openrouter",
    "deepseek",
}


def create_chat_model(
    provider: str,
    model: str,
    api_key: str,
    base_url: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1000,
    streaming: bool = False,
    response_format: dict | None = None,
) -> Any:
    if provider in _OPENAI_COMPATIBLE_PROVIDERS:
        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resolved_base_url = base_url
        if provider == "openrouter" and not resolved_base_url:
            resolved_base_url = "https://openrouter.ai/api/v1"
        elif provider == "deepseek" and not resolved_base_url:
            resolved_base_url = "https://api.deepseek.com"
        if streaming:
            kwargs["streaming"] = True
            kwargs["stream_usage"] = True
        if resolved_base_url:
            kwargs["base_url"] = resolved_base_url
        if response_format:
            kwargs["response_format"] = response_format
        return ChatOpenAI(**kwargs)

    if provider == "anthropic":
        return AnthropicChatModel(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )

    if provider == "google":
        raise NotImplementedError(
            "Provider google is not implemented yet. "
            "Install langchain-google-genai and add support."
        )

    raise ValueError(f"Unsupported provider: {provider}")
