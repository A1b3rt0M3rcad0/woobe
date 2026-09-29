from __future__ import annotations

from typing import Any


_TEXT_BLOCK_TYPES = {"", "text", "output_text"}
_INTERNAL_BLOCK_TYPES = {
    "reasoning",
    "reasoning_content",
    "thinking",
    "thought",
    "internal",
    "tool_use",
    "server_tool_call",
    "web_search_call",
}


class EmptyModelOutputError(RuntimeError):
    """Raised when a model call finishes without public user-facing output."""


def _public_result_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").lower()
        if block_type in _INTERNAL_BLOCK_TYPES or block_type not in _TEXT_BLOCK_TYPES:
            continue
        for key in ("text", "content", "delta"):
            value = block.get(key)
            if isinstance(value, str):
                parts.append(value)
                break
    return "".join(parts)


def has_public_output(answer: Any, parsed_output: Any = None) -> bool:
    if parsed_output is not None:
        return True
    return isinstance(answer, str) and bool(answer.strip())


def ensure_public_output(answer: Any, parsed_output: Any = None) -> None:
    if has_public_output(answer, parsed_output):
        return
    raise EmptyModelOutputError("Model completed without producing public output")


def model_result_has_public_output(result: Any) -> bool:
    """Return whether a Model result contains user-facing output."""

    return has_public_output(_public_result_text(result))


def ensure_model_result_has_public_output(result: Any) -> None:
    if model_result_has_public_output(result):
        return
    raise EmptyModelOutputError("Model completed without producing public output")
