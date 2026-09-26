from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from uuid import UUID

from modules.agent.application.strategy_sdk.model import StrategyPhase
from modules.agent.application.strategy_sdk.tools import StrategyToolSelection


@dataclass(frozen=True, slots=True)
class StrategyContextContribution:
    """Typed runtime contribution made available to context assembly."""

    key: str
    source_type: str
    content: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrategyInvocationContext:
    """Context materialized for one model invocation."""

    invocation_id: UUID
    messages: tuple[Any, ...]
    snapshot: Any | None = None


class StrategyContextManager(Protocol):
    """Context operations available to an Execution Strategy."""

    def has(self, key: str) -> bool: ...

    def set(self, contribution: StrategyContextContribution) -> None: ...

    def remove(self, key: str) -> None: ...

    async def assemble(
        self,
        *,
        phase: StrategyPhase | None = None,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyInvocationContext: ...
