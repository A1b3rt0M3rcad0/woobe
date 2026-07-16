from __future__ import annotations

from enum import StrEnum, auto


class UsageEventType(StrEnum):
    runtime_request = auto()
    llm_request = auto()
    embedding = auto()
    tool_call = auto()
    vector_query = auto()
    storage = auto()


class UsageUnit(StrEnum):
    request = auto()
    token = auto()
    call = auto()
    query = auto()
    mb_second = auto()
