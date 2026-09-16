from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class SuspensionReason(StrEnum):
    ASYNC_TOOL = "async_tool"
    HUMAN_APPROVAL = "human_approval"
    EXTERNAL_EVENT = "external_event"


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

    async def execute_many(
        self,
        tool_calls: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    ) -> StrategyToolBatch: ...
