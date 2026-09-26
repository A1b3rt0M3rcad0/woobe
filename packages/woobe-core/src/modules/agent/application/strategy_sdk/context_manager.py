from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from uuid import UUID

from modules.agent.application.strategy_sdk.contracts import ExecutionPhase
from modules.agent.application.strategy_sdk.tools import StrategyToolSelection


@dataclass(frozen=True, slots=True)
class StrategyContextContribution:
    """Typed runtime contribution made available to context assembly."""

    key: str
    source_type: str
    content: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrategyContextInspection:
    """Read-only pressure view used by a Strategy before choosing Context operations."""

    message_count: int
    contribution_count: int
    estimated_input_units: int
    usable_input_units: int | None
    utilization: float | None
    pressure: str


@dataclass(frozen=True, slots=True)
class StrategyInvocationContext:
    """Context materialized for one model invocation."""

    invocation_id: UUID
    messages: tuple[Any, ...]
    snapshot: Any | None = None


class StrategyContextManager(Protocol):
    """Context operations available to an Execution Strategy."""

    def inspect(self) -> StrategyContextInspection: ...

    def has(self, key: str) -> bool: ...

    def set(self, contribution: StrategyContextContribution) -> None: ...

    def remove(self, key: str) -> None: ...

    async def summarize(
        self,
        *,
        key: str = "session.summary",
        scope: str = "session",
        target_units: int = 2000,
        phase: str | ExecutionPhase | None = None,
    ) -> StrategyContextContribution: ...

    async def assemble(
        self,
        *,
        phase: str | ExecutionPhase | None = None,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyInvocationContext: ...

    async def assemble_final(
        self,
        *,
        reason: str,
        phase: str | ExecutionPhase,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyInvocationContext: ...
