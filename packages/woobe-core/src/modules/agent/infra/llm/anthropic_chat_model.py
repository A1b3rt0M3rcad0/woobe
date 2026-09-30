from __future__ import annotations

import asyncio
import json
from copy import copy
from typing import Any, AsyncIterator
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


_DEFAULT_BASE_URL = "https://api.anthropic.com"
_DEFAULT_VERSION = "2023-06-01"


class AnthropicChatModelError(RuntimeError):
    pass


def _tool_definition(value: dict[str, Any]) -> dict[str, Any]:
    function = value.get("function")
    if isinstance(function, dict):
        name = function.get("name")
        description = function.get("description")
        parameters = function.get("parameters")
    else:
        name = value.get("name")
        description = value.get("description")
        parameters = value.get("input_schema")

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Anthropic Tool definition requires a name")

    return {
        "name": name,
        "description": str(description or ""),
        "input_schema": (
            dict(parameters)
            if isinstance(parameters, dict)
            else {"type": "object", "properties": {}}
        ),
    }


def _assistant_content(message: AIMessage) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    content = message.content
    if isinstance(content, str) and content:
        blocks.append({"type": "text", "text": content})
    elif isinstance(content, list):
        for item in content:
            if isinstance(item, str) and item:
                blocks.append({"type": "text", "text": item})
            elif isinstance(item, dict):
                item_type = item.get("type")
                if item_type == "text" and isinstance(item.get("text"), str):
                    blocks.append({"type": "text", "text": item["text"]})

    for tool_call in getattr(message, "tool_calls", None) or []:
        name = tool_call.get("name")
        if not isinstance(name, str) or not name:
            continue
        blocks.append(
            {
                "type": "tool_use",
                "id": str(tool_call.get("id") or ""),
                "name": name,
                "input": (
                    dict(tool_call.get("args") or {})
                    if isinstance(tool_call.get("args"), dict)
                    else {}
                ),
            }
        )
    return blocks


def _append_message(
    target: list[dict[str, Any]],
    *,
    role: str,
    content: list[dict[str, Any]],
) -> None:
    if not content:
        return
    if target and target[-1]["role"] == role:
        target[-1]["content"].extend(content)
        return
    target.append({"role": role, "content": content})


def _anthropic_messages(
    messages: list[BaseMessage],
) -> tuple[str | None, list[dict[str, Any]]]:
    system_parts: list[str] = []
    result: list[dict[str, Any]] = []

    for message in messages:
        if isinstance(message, SystemMessage):
            content = message.content
            if isinstance(content, str) and content:
                system_parts.append(content)
            continue

        if isinstance(message, ToolMessage):
            _append_message(
                result,
                role="user",
                content=[
                    {
                        "type": "tool_result",
                        "tool_use_id": str(message.tool_call_id),
                        "content": str(message.content or ""),
                    }
                ],
            )
            continue

        if isinstance(message, AIMessage):
            _append_message(
                result,
                role="assistant",
                content=_assistant_content(message),
            )
            continue

        content = message.content
        blocks: list[dict[str, Any]] = []
        if isinstance(content, str):
            blocks.append({"type": "text", "text": content})
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, str):
                    blocks.append({"type": "text", "text": item})
                elif isinstance(item, dict):
                    item_type = item.get("type")
                    if item_type in {"text", "image"}:
                        blocks.append(dict(item))
        _append_message(result, role="user", content=blocks)

    return (
        "\n\n".join(system_parts) if system_parts else None,
        result,
    )


def _post_json(
    url: str,
    *,
    api_key: str,
    payload: dict[str, Any],
    anthropic_version: str,
    timeout: int = 120,
) -> dict[str, Any]:
    request = UrlRequest(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Woobe/0.14.0",
            "X-Api-Key": api_key,
            "anthropic-version": anthropic_version,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise AnthropicChatModelError(
            f"Anthropic request failed with HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise AnthropicChatModelError(
            f"Anthropic request failed: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise AnthropicChatModelError("Anthropic request timed out") from exc

    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AnthropicChatModelError(
            "Anthropic returned invalid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise AnthropicChatModelError(
            "Anthropic returned an unsupported response"
        )
    return value


class AnthropicChatModel:
    """Minimal LangChain-message compatibility adapter for Anthropic Messages API.

    This object intentionally implements only the runtime surface Woobe requires.
    Provider wire semantics remain in infrastructure and never leak into Strategy
    contracts.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        response_format: dict[str, Any] | None = None,
        anthropic_version: str = _DEFAULT_VERSION,
        tools: tuple[dict[str, Any], ...] = (),
        tool_choice: str | None = None,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format = dict(response_format or {})
        self.anthropic_version = anthropic_version
        self.tools = tuple(dict(tool) for tool in tools)
        self.tool_choice = tool_choice

    def bind_tools(
        self,
        tools: list[dict[str, Any]],
        *,
        tool_choice: str = "auto",
        **_: Any,
    ) -> AnthropicChatModel:
        bound = copy(self)
        bound.tools = tuple(_tool_definition(tool) for tool in tools)
        bound.tool_choice = tool_choice
        return bound

    def _payload(self, messages: list[BaseMessage]) -> dict[str, Any]:
        system, provider_messages = _anthropic_messages(messages)
        if self.response_format.get("type") == "json_object":
            json_instruction = "Return only a valid JSON object with no markdown."
            system = (
                f"{system}\n\n{json_instruction}"
                if system
                else json_instruction
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": provider_messages,
        }
        if system:
            payload["system"] = system
        if self.tools:
            payload["tools"] = list(self.tools)
            if self.tool_choice == "auto":
                payload["tool_choice"] = {"type": "auto"}
            elif self.tool_choice == "required":
                payload["tool_choice"] = {"type": "any"}
            elif self.tool_choice == "none":
                pass
        return payload

    @staticmethod
    def _result(payload: dict[str, Any]) -> AIMessage:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        content = payload.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text" and isinstance(block.get("text"), str):
                    text_parts.append(block["text"])
                elif block_type == "tool_use":
                    name = block.get("name")
                    if isinstance(name, str) and name:
                        tool_calls.append(
                            {
                                "id": str(block.get("id") or ""),
                                "name": name,
                                "args": (
                                    dict(block.get("input") or {})
                                    if isinstance(block.get("input"), dict)
                                    else {}
                                ),
                                "type": "tool_call",
                            }
                        )

        usage = payload.get("usage")
        usage_dict = usage if isinstance(usage, dict) else {}
        input_tokens = usage_dict.get("input_tokens")
        output_tokens = usage_dict.get("output_tokens")
        usage_metadata = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": (
                input_tokens + output_tokens
                if isinstance(input_tokens, int)
                and isinstance(output_tokens, int)
                else None
            ),
        }

        return AIMessage(
            content="".join(text_parts),
            tool_calls=tool_calls,
            usage_metadata=usage_metadata,
            response_metadata={
                "provider": "anthropic",
                "model": payload.get("model"),
                "finish_reason": payload.get("stop_reason"),
                "usage": usage_dict,
            },
        )

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage:
        payload = await asyncio.to_thread(
            _post_json,
            f"{self.base_url}/v1/messages",
            api_key=self.api_key,
            payload=self._payload(messages),
            anthropic_version=self.anthropic_version,
        )
        return self._result(payload)

    async def astream(
        self,
        messages: list[BaseMessage],
    ) -> AsyncIterator[AIMessage]:
        # Compatibility streaming: one complete provider result. The Woobe runtime
        # protocol remains intact while native Anthropic SSE can be introduced later
        # without changing Model/Execution contracts.
        yield await self.ainvoke(messages)


__all__ = [
    "AnthropicChatModel",
    "AnthropicChatModelError",
]
