from __future__ import annotations

import json
from typing import Any

from modules.agent.application.interfaces.execution_context import current_execution

DEFAULT_MAX_TOOL_MESSAGE_CHARS = 16_000
DEFAULT_MAX_LIST_ITEMS = 12
DEFAULT_MAX_DICT_ITEMS = 40
DEFAULT_MAX_DEPTH = 5

_LARGE_TEXT_KEYS = {
    "body",
    "content",
    "html",
    "markdown",
    "readme",
    "raw",
    "text",
}

_PRIORITY_KEYS = (
    "success",
    "error",
    "result",
    "output",
    "body",
    "items",
    "data",
    "repository",
    "repo",
    "full_name",
    "name",
    "title",
    "url",
    "html_url",
    "clone_url",
    "ssh_url",
    "description",
    "message",
)


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _truncate_text(value: str, *, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    omitted = len(value) - max_chars
    return f"{value[:max_chars]}... [truncated {omitted} chars]"


def _compact_value(
    value: Any,
    *,
    depth: int = 0,
    max_string_chars: int,
) -> Any:
    if depth >= DEFAULT_MAX_DEPTH:
        if isinstance(value, (dict, list, tuple)):
            return f"[truncated nested {type(value).__name__}]"
        if isinstance(value, str):
            return _truncate_text(value, max_chars=max_string_chars)
        return value

    if isinstance(value, str):
        return _truncate_text(value, max_chars=max_string_chars)

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    if isinstance(value, (list, tuple)):
        compacted = [
            _compact_value(
                item,
                depth=depth + 1,
                max_string_chars=max_string_chars,
            )
            for item in list(value)[:DEFAULT_MAX_LIST_ITEMS]
        ]
        omitted = len(value) - len(compacted)
        if omitted > 0:
            compacted.append({"_truncated_items": omitted})
        return compacted

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        seen: set[str] = set()
        keys = [key for key in _PRIORITY_KEYS if key in value]
        keys.extend(key for key in value.keys() if key not in seen and key not in keys)

        for key in keys:
            if len(result) >= DEFAULT_MAX_DICT_ITEMS:
                break
            seen.add(str(key))
            child = value.get(key)
            key_text = str(key)
            if isinstance(child, str) and key_text.lower() in _LARGE_TEXT_KEYS:
                result[key_text] = _truncate_text(
                    child,
                    max_chars=max_string_chars,
                )
            else:
                result[key_text] = _compact_value(
                    child,
                    depth=depth + 1,
                    max_string_chars=max_string_chars,
                )

        omitted = len(value) - len(result)
        if omitted > 0:
            result["_truncated_keys"] = omitted
        return result

    return str(value)


def _resolve_max_chars(configured: int | None) -> int:
    if isinstance(configured, int) and not isinstance(configured, bool) and configured > 0:
        return configured

    context = current_execution.get()
    runtime_limit = getattr(context, "tool_result_max_chars", None) if context else None
    if isinstance(runtime_limit, int) and not isinstance(runtime_limit, bool) and runtime_limit > 0:
        return runtime_limit
    return DEFAULT_MAX_TOOL_MESSAGE_CHARS


def compact_tool_output_for_llm(
    output: Any,
    *,
    max_chars: int | None = None,
) -> str:
    """Return a bounded tool-output payload safe to send back to the LLM.

    Raw tool output can be very large and is still kept separately in ToolCallInfo
    and trace payloads. This function is only for ToolMessage content, i.e. the
    context sent back to the model after a tool call. Network executions may
    override the materialization ceiling through their runtime settings.
    """
    resolved_max_chars = _resolve_max_chars(max_chars)
    raw_text = _json_dumps(output)
    compacted = _compact_value(
        output,
        max_string_chars=resolved_max_chars,
    )
    compacted_text = _json_dumps(compacted)

    envelope = {
        "tool_output": compacted,
        "_llm_compacted": (
            len(raw_text) != len(compacted_text)
            or len(compacted_text) > resolved_max_chars
        ),
        "_original_size_chars": len(raw_text),
        "_llm_size_chars": min(len(compacted_text), resolved_max_chars),
    }
    text = _json_dumps(envelope)
    if len(text) <= resolved_max_chars:
        return text

    omitted = len(text) - resolved_max_chars
    return _json_dumps(
        {
            "tool_output_preview": text[:resolved_max_chars],
            "_llm_compacted": True,
            "_original_size_chars": len(raw_text),
            "_truncated_chars": omitted,
            "_warning": "Tool output was compacted before being sent back to the LLM. Full output remains available in trace/tool call data.",
        }
    )
