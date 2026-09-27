from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol

from modules.agent.application.strategy_sdk.contracts import ExecutionPhase
from modules.agent.application.strategy_sdk.invocation import StrategyInvocation
from modules.agent.application.strategy_sdk.knowledge import StrategyKnowledgeResult
from modules.agent.application.strategy_sdk.tools import StrategyToolSelection


class StrategyContextTarget(StrEnum):
    PRIMARY = "primary"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class StrategyContextContribution:
    """Typed runtime contribution made available to context assembly."""

    key: str
    source_type: str
    content: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrategyContextInspection:
    """Read-only pressure view produced by the configured Context Manager."""

    message_count: int
    contribution_count: int
    estimated_input_units: int
    usable_input_units: int | None
    utilization: float | None
    pressure: str


@dataclass(frozen=True, slots=True)
class StrategyContextCompactionResult:
    """Outcome of one Context Manager compaction decision."""

    changed: bool
    upserted_keys: tuple[str, ...] = ()
    removed_keys: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class StrategyContextManager(Protocol):
    """Context operations available to an Execution Strategy."""

    def inspect(self) -> StrategyContextInspection: ...

    def has(self, key: str) -> bool: ...

    def set(self, contribution: StrategyContextContribution) -> None: ...

    def remove(self, key: str) -> None: ...

    def include_knowledge(self, result: StrategyKnowledgeResult) -> None: ...

    async def compact(
        self,
        *,
        phase: str | ExecutionPhase | None = None,
    ) -> StrategyContextCompactionResult: ...

    async def prepare(
        self,
        *,
        tools: StrategyToolSelection,
        phase: str | ExecutionPhase | None = None,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
    ) -> StrategyInvocation: ...

    async def prepare_final(
        self,
        *,
        reason: str,
        phase: str | ExecutionPhase,
        tools: StrategyToolSelection,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
    ) -> StrategyInvocation: ...
