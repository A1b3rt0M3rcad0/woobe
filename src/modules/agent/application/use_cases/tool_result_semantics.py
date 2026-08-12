from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class NormalizedToolResult:
    success: bool
    status: str
    error_code: str | None = None
    error_message: str | None = None


_ERROR_PATTERNS: tuple[tuple[str, str], ...] = (
    ("invalid reponame format", "invalid_repository_identifier"),
    ("repository not found", "repository_not_found"),
    ("error processing question", "mcp_application_error"),
)
_PROTOCOL_CONTAINER_KEYS = {"output", "body", "mcp"}


def _as_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _walk(value: Any, depth: int = 0) -> Iterator[Any]:
    if depth > 8:
        return
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child, depth + 1)


def _protocol_candidates(value: Any, depth: int = 0) -> Iterator[dict[str, Any]]:
    if depth > 6 or not isinstance(value, dict):
        return
    yield value
    for key, child in value.items():
        if key in _PROTOCOL_CONTAINER_KEYS and isinstance(child, dict):
            yield from _protocol_candidates(child, depth + 1)


def _known_error(value: Any) -> tuple[str, str] | None:
    for candidate in _walk(value):
        message = _as_text(candidate)
        if not message:
            continue
        normalized = " ".join(message.lower().split())
        for pattern, code in _ERROR_PATTERNS:
            if pattern in normalized:
                return code, message
    return None


def _explicit_error(candidate: dict[str, Any]) -> tuple[str | None, str] | None:
    error = candidate.get("error")
    if isinstance(error, dict):
        message = _as_text(error.get("message")) or _as_text(error.get("detail"))
        if message:
            known = _known_error(error)
            return (
                known[0] if known else _as_text(error.get("code")),
                known[1] if known else message,
            )
    else:
        message = _as_text(error)
        if message:
            known = _known_error(message)
            return (known[0] if known else None, known[1] if known else message)
    return None


def _structured_error(value: Any) -> tuple[str | None, str] | None:
    for candidate in _protocol_candidates(value):
        explicit = _explicit_error(candidate)
        if explicit:
            return explicit

        if candidate.get("isError") is True or candidate.get("is_error") is True:
            known = _known_error(candidate)
            message = (
                _as_text(candidate.get("message"))
                or _as_text(candidate.get("content"))
                or "The Tool reported an application error."
            )
            return (
                known[0] if known else "tool_application_error",
                known[1] if known else message,
            )

        status = _as_text(candidate.get("status"))
        if status and status.lower() in {"error", "failed", "failure"}:
            known = _known_error(candidate)
            message = (
                _as_text(candidate.get("message"))
                or "The Tool reported a failed result."
            )
            return (
                known[0] if known else "tool_application_error",
                known[1] if known else message,
            )

        structured_content = candidate.get("structuredContent")
        if not isinstance(structured_content, dict):
            structured_content = candidate.get("structured_content")
        if isinstance(structured_content, dict):
            known = _known_error(structured_content.get("result"))
            if known:
                return known

    return None


def normalize_tool_result(output: Any) -> NormalizedToolResult:
    if isinstance(output, dict) and output.get("success") is False:
        explicit_error = _structured_error(output)
        return NormalizedToolResult(
            success=False,
            status="error",
            error_code=(explicit_error[0] if explicit_error else None)
            or "tool_execution_failed",
            error_message=(
                explicit_error[1]
                if explicit_error
                else _as_text(output.get("error"))
            )
            or "Tool execution failed.",
        )

    semantic_error = _structured_error(output)
    if semantic_error:
        return NormalizedToolResult(
            success=False,
            status="error",
            error_code=semantic_error[0] or "tool_application_error",
            error_message=semantic_error[1],
        )

    return NormalizedToolResult(success=True, status="success")
