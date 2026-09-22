from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI


_OPENAI_COMPATIBLE_PROVIDERS = {"openai", "custom", "openrouter"}


class _DeepSeekCompatibleChatOpenAI(ChatOpenAI):
    """Preserve DeepSeek thinking metadata across multi-turn Tool calls."""

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        messages = self._convert_input(input_).to_messages()
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        serialized = payload.get("messages")
        if not isinstance(serialized, list):
            return payload

        for original, item in zip(messages, serialized, strict=False):
            if not isinstance(original, AIMessage) or not isinstance(item, dict):
                continue
            reasoning = original.additional_kwargs.get("reasoning_content")
            item["reasoning_content"] = reasoning if isinstance(reasoning, str) else ""

        return payload

    def _create_chat_result(
        self,
        response: dict | Any,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        response_dict = response if isinstance(response, dict) else response.model_dump()
        choices = response_dict.get("choices")
        if not isinstance(choices, list):
            return result

        for generation, choice in zip(result.generations, choices, strict=False):
            if not isinstance(generation.message, AIMessage) or not isinstance(choice, dict):
                continue
            raw_message = choice.get("message")
            if not isinstance(raw_message, dict):
                continue
            reasoning = raw_message.get("reasoning_content")
            if not isinstance(reasoning, str):
                reasoning = raw_message.get("reasoning")
            if isinstance(reasoning, str):
                generation.message.additional_kwargs["reasoning_content"] = reasoning

        return result

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        generation = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if generation is None or not isinstance(generation.message, AIMessageChunk):
            return generation

        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices") or []
        if not choices or not isinstance(choices[0], dict):
            return generation
        delta = choices[0].get("delta")
        if not isinstance(delta, dict):
            return generation

        reasoning = delta.get("reasoning_content")
        if not isinstance(reasoning, str):
            reasoning = delta.get("reasoning")
        if isinstance(reasoning, str):
            generation.message.additional_kwargs["reasoning_content"] = reasoning
        return generation


def _chat_model_class(model: str) -> type[ChatOpenAI]:
    if "deepseek" in model.lower():
        return _DeepSeekCompatibleChatOpenAI
    return ChatOpenAI


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
        return _chat_model_class(model)(**kwargs)

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
