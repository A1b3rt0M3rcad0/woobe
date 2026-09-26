from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.strategy_sdk.model import StrategyPhase


@dataclass(frozen=True, slots=True)
class StrategyKnowledgeResult:
    """Knowledge retrieval result exposed to Execution Strategies."""

    content: str | None
    sources: tuple[SourceInfo, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.content)


class StrategyKnowledge(Protocol):
    """Knowledge operations available to an Execution Strategy."""

    async def retrieve(
        self,
        *,
        query: str | None = None,
        phase: StrategyPhase | None = None,
    ) -> StrategyKnowledgeResult: ...
