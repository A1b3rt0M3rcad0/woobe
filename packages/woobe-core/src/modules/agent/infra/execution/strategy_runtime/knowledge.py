from __future__ import annotations

from modules.agent.application.strategy_sdk import (
    StrategyKnowledgeResult,
    StrategyPhase,
)
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)


class RuntimeStrategyKnowledge:
    """Strategy-facing Knowledge facade backed by the frozen runtime binding."""

    __slots__ = ("_capability",)

    def __init__(self, *, capability: KnowledgeRetrievalCapability) -> None:
        self._capability = capability

    async def retrieve(
        self,
        *,
        query: str | None = None,
        phase: StrategyPhase | None = None,
    ) -> StrategyKnowledgeResult:
        del phase
        result = await self._capability.retrieve(query=query)
        return StrategyKnowledgeResult(
            content=result.content,
            sources=result.sources,
            metadata=result.metadata,
        )
