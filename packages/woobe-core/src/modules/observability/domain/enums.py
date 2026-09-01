from __future__ import annotations

from enum import StrEnum, auto


class TraceStatus(StrEnum):
    pending = auto()
    running = auto()
    completed = auto()
    failed = auto()
    cancelled = auto()


class TraceEventType(StrEnum):
    llm_call = auto()
    tool_call = auto()
    vector_query = auto()
    error = auto()
    warning = auto()
    info = auto()
