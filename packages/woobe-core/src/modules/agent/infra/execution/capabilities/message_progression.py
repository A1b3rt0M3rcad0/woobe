from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

_TERMINAL_RESPONSE_INSTRUCTION = (
    "Generate one single final user-facing answer for the latest user request. "
    "Fulfill every part of that request completely and in the same order the user asked. "
    "Use successful capability results exactly where relevant. Explain failed "
    "capability-dependent parts accurately and ask for missing information when required. "
    "Do not invent identifiers or fabricate successful results. Do not call capabilities. "
    "Do not mention internal execution phases."
)


def message_content(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    return ""


def is_user_message(message: Any) -> bool:
    role = getattr(message, "role", None)
    message_type = getattr(message, "type", None)
    class_name = message.__class__.__name__
    return role == "user" or message_type in {"human", "user"} or class_name == "HumanMessage"


def is_tool_message(message: Any) -> bool:
    role = getattr(message, "role", None)
    message_type = getattr(message, "type", None)
    class_name = message.__class__.__name__
    return role == "tool" or message_type == "tool" or class_name == "ToolMessage"


def sanitize_base_messages(messages: list) -> list:
    """Remove historical raw Tool payloads before a fresh strategy execution."""
    sanitized: list = []
    for message in messages:
        if is_tool_message(message):
            continue
        if getattr(message, "tool_calls", None):
            sanitized.append(AIMessage(content=message_content(message)))
        else:
            sanitized.append(message)
    return sanitized


def has_tool_calls(result: Any) -> bool:
    return bool(getattr(result, "tool_calls", None))


def latest_user_request(messages: list) -> str:
    for message in reversed(messages):
        if is_user_message(message):
            content = message_content(message).strip()
            if content:
                return content
    return ""


def _json_preview(value: Any, *, max_chars: int = 1200) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def _extract_capability_result(output: Any) -> Any:
    if not isinstance(output, dict):
        return output
    if "result" in output:
        return output["result"]
    nested = output.get("output")
    if isinstance(nested, dict):
        if "result" in nested:
            return nested["result"]
        body = nested.get("body")
        if isinstance(body, dict) and "result" in body:
            return body["result"]
        if body is not None:
            return body
    return output


def capability_results_summary(tool_calls: list[Any]) -> str:
    if not tool_calls:
        return ""
    lines: list[str] = []
    for index, call in enumerate(tool_calls, start=1):
        capability_name = getattr(call, "tool_name", None) or "capability"
        capability_input = getattr(call, "input", None)
        output = getattr(call, "output", None)
        success = getattr(call, "success", None)
        error_code = getattr(call, "error_code", None)
        error = getattr(call, "error", None)
        result = _extract_capability_result(output)
        status = "success" if success is not False else "failed"
        input_preview = _json_preview(capability_input) if capability_input is not None else "{}"
        if success is False:
            code = f" [{error_code}]" if error_code else ""
            result_preview = f"error{code}: {error or 'Capability execution failed'}"
        else:
            result_preview = _json_preview(result)
        lines.append(
            f"{index}. {capability_name}({input_preview}) -> {status}: {result_preview}"
        )
    return "\n".join(lines)


def build_terminal_response_instruction(
    *,
    messages: list,
    final_json_instruction: str | None,
    tool_calls: list[Any],
    stopped_reason: str | None,
) -> str:
    latest_request = latest_user_request(messages)
    request_block = (
        f"\n\nLatest user request:\n<user_request>\n{latest_request}\n</user_request>"
        if latest_request
        else ""
    )
    capability_results = capability_results_summary(tool_calls)
    capability_results_block = (
        "\n\nCapability results:\n"
        f"<capability_results>\n{capability_results}\n</capability_results>"
        if capability_results
        else ""
    )
    stopped_block = ""
    if stopped_reason:
        stopped_block = (
            "\n\nCapability execution was stopped before another attempt because of: "
            f"{stopped_reason}. Use available successful results, explain failed parts, "
            "and request any missing identifier or input. Do not call another capability."
        )
    json_block = (
        "\n\nStructured output requirement:\n"
        f"{final_json_instruction}"
        if final_json_instruction
        else ""
    )
    return (
        f"{_TERMINAL_RESPONSE_INSTRUCTION}"
        f"{request_block}"
        f"{capability_results_block}"
        f"{stopped_block}"
        "\n\nUse the capability results block as the normalized source of truth. "
        "The terminal response intentionally receives compact results instead of raw "
        "capability payloads. Do not omit non-capability parts of the latest user request."
        f"{json_block}"
    )


def terminal_response_messages(
    messages: list,
    final_json_instruction: str | None,
    tool_calls: list[Any],
    stopped_reason: str | None,
) -> list:
    return [
        *messages,
        SystemMessage(
            content=build_terminal_response_instruction(
                messages=messages,
                final_json_instruction=final_json_instruction,
                tool_calls=tool_calls,
                stopped_reason=stopped_reason,
            )
        ),
    ]
