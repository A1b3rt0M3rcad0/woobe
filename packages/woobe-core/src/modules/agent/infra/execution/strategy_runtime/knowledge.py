from __future__ import annotations

import time

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.strategy_sdk import (
    StrategyKnowledgeResult,
    StrategyPhase,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)
from modules.agent.infra.execution.execution_instrumentation import utc_iso
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream
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
        effective_query = (
            query if query is not None else self._capability.default_query
        )
        if self._capability.retrieve_fn is None or not effective_query:
            return StrategyKnowledgeResult(content=None)

        normalized_phase = strategy_phase_value(phase or "knowledge_retrieval")
        execution_context = current_execution.get()
        recorder = (
            execution_context.run_event_recorder
            if execution_context is not None
            else None
        )
        started_at = utc_iso()
        started = time.monotonic()

        if recorder is not None:
            await recorder.emit(
                "knowledge.retrieval.started",
                {
                    "phase": normalized_phase,
                    "query": effective_query,
                },
            )

        try:
            result = await self._capability.retrieve(query=effective_query)
        except Exception as exc:
            ended_at = utc_iso()
            metadata = (
                dict(execution_context.rag_metadata or {})
                if execution_context is not None
                else {}
            )
            call = {
                "phase": normalized_phase,
                "query": effective_query,
                "status": "error",
                "error": str(exc),
                "found": False,
                "source_count": 0,
                "metadata": metadata,
                "started_at": started_at,
                "ended_at": ended_at,
                "occurred_at": ended_at,
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
            self._runtime_state.record_knowledge_call(call, ())

            if execution_context is not None:
                execution_context.context_rag_sources = []
            if recorder is not None:
                await recorder.emit(
                    "knowledge.retrieval.failed",
                    {
                        "phase": normalized_phase,
                        "query": effective_query,
                        "error": str(exc),
                        "metadata": metadata,
                    },
                )
            raise

        ended_at = utc_iso()
        serialized_sources = [
            source.model_dump(mode="json")
            for source in result.sources
        ]
        call = {
            "phase": normalized_phase,
            "query": effective_query,
            "status": "success",
            "found": bool(result.content),
            "source_count": len(result.sources),
            "metadata": dict(result.metadata),
            "started_at": started_at,
            "ended_at": ended_at,
            "occurred_at": ended_at,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
        self._runtime_state.record_knowledge_call(call, result.sources)

        if execution_context is not None:
            execution_context.context_rag_sources = serialized_sources
            if recorder is not None:
                await recorder.emit(
                    "knowledge.retrieval.completed",
                    {
                        "phase": normalized_phase,
                        "query": effective_query,
                        "found": bool(result.content),
                        "source_count": len(result.sources),
                        "sources": serialized_sources,
                        "metadata": dict(result.metadata),
                    },
                )

        stream = current_runtime_stream.get()
        if stream is not None and serialized_sources:
            await stream.emit(
                "sources",
                sources=serialized_sources,
            )

        return StrategyKnowledgeResult(
            content=result.content,
            sources=result.sources,
            metadata=result.metadata,
        )
