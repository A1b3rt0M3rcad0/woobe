from __future__ import annotations

from typing import Any

from modules.agent.runtime.runtime_streaming import extract_chunk_text


class EmptyModelOutputError(RuntimeError):
    """Raised when a model call finishes without public user-facing output."""


def has_public_output(answer: Any, parsed_output: Any = None) -> bool:
    if parsed_output is not None:
        return True
    return isinstance(answer, str) and bool(answer.strip())


def ensure_public_output(answer: Any, parsed_output: Any = None) -> None:
    if has_public_output(answer, parsed_output):
        return
    raise EmptyModelOutputError(
        "Model completed without producing public output"
    )


def ensure_model_result_has_public_output(result: Any) -> None:
    ensure_public_output(extract_chunk_text(result))
