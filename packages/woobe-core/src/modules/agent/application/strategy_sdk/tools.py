from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class SuspensionReason(StrEnum):
    ASYNC_TOOL = "async_tool"
    HUMAN_APPROVAL = "human_approval"
    EXTERNAL_EVENT = "external_event"


class StrategyToolSelectionMode(StrEnum):
    ALL = "all"
    NONE = "none"
    EXPLICIT = "explicit"


@dataclass(frozen=True, slots=True)
class StrategyToolSelection:
    """Invocation-scoped subset of the tools authorized by the runtime."""

    mode: StrategyToolSelectionMode
    names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode is StrategyToolSelectionMode.EXPLICIT and not self.names:
            raise ValueError("Explicit tool selection requires at least one tool name")
        if self.mode is not StrategyToolSelectionMode.EXPLICIT and self.names:
            raise ValueError("Only explicit tool selection may contain tool names")


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

    def all(self) -> StrategyToolSelection: ...

    def none(self) -> StrategyToolSelection: ...

    def select(self, *names: str) -> StrategyToolSelection: ...

    async def execute_many(
        self,
        tool_calls: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> StrategyToolBatch: ...
