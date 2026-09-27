from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Protocol


class SuspensionReason(StrEnum):
    ASYNC_TOOL = "async_tool"
    HUMAN_APPROVAL = "human_approval"
    EXTERNAL_EVENT = "external_event"


class StrategyToolSelectionMode(StrEnum):
    ALL = "all"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class StrategyToolSelection:
    """Whether one Model invocation receives all authorized Tools or none."""

    mode: StrategyToolSelectionMode


@dataclass(frozen=True, slots=True)
class StrategyToolCall:
    """Framework-neutral Tool call produced by a Model."""

    id: str | None
    name: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Strategy Tool call name must not be empty")

    def as_runtime_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "args": dict(self.arguments),
        }


@dataclass(frozen=True, slots=True)
class StrategyToolBatch:
    """Tool results normalized for strategy-level orchestration."""

    results: tuple[dict[str, Any], ...]
    messages: tuple[Any, ...]
    has_failures: bool
    requires_suspension: bool = False
    suspension_reason: SuspensionReason | None = None
    operation_ref: str | None = None


class StrategyTools(Protocol):
    """Tool operations available to an Execution Strategy."""

    @property
    def has_any(self) -> bool: ...

    def all(self) -> StrategyToolSelection: ...

    def none(self) -> StrategyToolSelection: ...

    async def execute_many(
        self,
        tool_calls: list[StrategyToolCall] | tuple[StrategyToolCall, ...],
    ) -> StrategyToolBatch: ...
