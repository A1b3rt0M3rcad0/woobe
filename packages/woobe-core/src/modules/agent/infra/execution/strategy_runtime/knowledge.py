from __future__ import annotations

from modules.agent.application.strategy_sdk import (
    StrategyKnowledgeResult,
    StrategyPhase,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)
from modules.agent.infra.execution.execution_instrumentation import utc_iso
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


class RuntimeStrategyKnowledge:
    """Strategy-facing Knowledge facade backed by the frozen runtime binding."""

    __slots__ = ("_capability", "_runtime_state")

    def __init__(
        self,
        *,
        capability: KnowledgeRetrievalCapability,
        runtime_state: StrategyRuntimeState,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state

    async def retrieve(
        self,
        *,
        query: str | None = None,
        phase: StrategyPhase | None = None,
    ) -> StrategyKnowledgeResult:
        result = await self._capability.retrieve(query=query)
        normalized_phase = strategy_phase_value(phase or "knowledge_retrieval")
        occurred_at = utc_iso()
        call = {
            "phase": normalized_phase,
            "query": query,
            "found": bool(result.content),
            "source_count": len(result.sources),
            "metadata": dict(result.metadata),
            "occurred_at": occurred_at,
        }
        self._runtime_state.record_knowledge_call(call, result.sources)
        return StrategyKnowledgeResult(
            content=result.content,
            sources=result.sources,
            metadata=result.metadata,
        )
