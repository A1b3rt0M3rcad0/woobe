from __future__ import annotations

import time
from collections.abc import Mapping

from modules.agent.application.interfaces.execution import source_info_from_knowledge_source
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.knowledge import (
    KnowledgeCapabilities,
    KnowledgeRequest,
    KnowledgeResult,
    KnowledgeStrategy,
)
from modules.agent.application.strategy_sdk import (
    StrategyConversation,
    StrategyKnowledgeResult,
    StrategyKnowledgeSource,
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


class _ObservedKnowledgeCapabilities(KnowledgeCapabilities):
    """Capture the concrete query without moving query policy back into Runtime."""

    __slots__ = ("_capability", "_phase", "_recorder", "query")

    def __init__(
        self,
        *,
        capability: KnowledgeRetrievalCapability,
        phase: str,
        recorder,
    ) -> None:
        self._capability = capability
        self._phase = phase
        self._recorder = recorder
        self.query: str | None = None

    @property
    def available(self) -> bool:
        return self._capability.available

    async def retrieve(self, *, query: str) -> KnowledgeResult:
        self.query = query
        if self._recorder is not None:
            await self._recorder.emit(
                "knowledge.retrieval.started",
                {
                    "phase": self._phase,
                    "query": query,
                },
            )
        return await self._capability.retrieve(query=query)


class RuntimeStrategyKnowledge:
    """Execution-facing facade over the selected programmable Knowledge Strategy."""

    __slots__ = (
        "_capability",
        "_runtime_state",
        "_strategy",
        "_runtime_config",
    )

    def __init__(
        self,
        *,
        capability: KnowledgeRetrievalCapability,
        runtime_state: StrategyRuntimeState,
        strategy: KnowledgeStrategy | None = None,
        runtime_config: Mapping[str, object] | None = None,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state
        self._strategy = strategy
        self._runtime_config = dict(runtime_config or {})

    async def retrieve(
        self,
        *,
        conversation: StrategyConversation,
        phase: StrategyPhase | None = None,
    ) -> StrategyKnowledgeResult:
        strategy = self._strategy
        if strategy is None:
            if not self._capability.available:
                return StrategyKnowledgeResult(content=None)
            raise RuntimeError("No Knowledge Strategy was selected for this execution")

        normalized_phase = strategy_phase_value(phase or "knowledge_retrieval")
        execution_context = current_execution.get()
        recorder = (
            execution_context.run_event_recorder
            if execution_context is not None
            else None
        )
        observed = _ObservedKnowledgeCapabilities(
            capability=self._capability,
            phase=normalized_phase,
            recorder=recorder,
        )
        started_at = utc_iso()
        started = time.monotonic()

        try:
            result = await strategy.retrieve(
                KnowledgeRequest(
                    conversation=conversation,
                    runtime_config=self._runtime_config,
                ),
                observed,
            )
        except Exception as exc:
            ended_at = utc_iso()
            raw_metadata = getattr(exc, "rag_metadata", None)
            metadata = (
                dict(raw_metadata)
                if isinstance(raw_metadata, dict)
                else {}
            )
            metadata.setdefault("knowledge_strategy", strategy.name)
            query = observed.query
            call = {
                "phase": normalized_phase,
                "query": query,
                "strategy": strategy.name,
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
                execution_context.knowledge_metadata = dict(metadata)
                execution_context.knowledge_sources = []
                execution_context.rag_metadata = dict(metadata)
                execution_context.context_rag_sources = []
            if recorder is not None:
                await recorder.emit(
                    "knowledge.retrieval.failed",
                    {
                        "phase": normalized_phase,
                        "query": query,
                        "strategy": strategy.name,
                        "error": str(exc),
                        "metadata": metadata,
                    },
                )
            raise

        query = result.query or observed.query
        if query is None and not result.found and not result.sources:
            return StrategyKnowledgeResult(
                content=result.content,
                query=None,
                metadata=result.metadata,
            )

        ended_at = utc_iso()
        serialized_sources = [source.as_dict() for source in result.sources]
        evidence_sources = tuple(
            source_info_from_knowledge_source(source)
            for source in result.sources
        )
        metadata = {
            "knowledge_strategy": strategy.name,
            **dict(result.metadata),
        }
        if execution_context is not None:
            execution_context.knowledge_metadata = dict(metadata)
            execution_context.rag_metadata = dict(metadata)
        call = {
            "phase": normalized_phase,
            "query": query,
            "strategy": strategy.name,
            "status": "success",
            "found": bool(result.content),
            "source_count": len(result.sources),
            "metadata": metadata,
            "started_at": started_at,
            "ended_at": ended_at,
            "occurred_at": ended_at,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
        self._runtime_state.record_knowledge_call(call, evidence_sources)

        if execution_context is not None:
            execution_context.knowledge_sources = list(serialized_sources)
            execution_context.context_rag_sources = list(serialized_sources)
            if recorder is not None:
                await recorder.emit(
                    "knowledge.retrieval.completed",
                    {
                        "phase": normalized_phase,
                        "query": query,
                        "strategy": strategy.name,
                        "found": bool(result.content),
                        "source_count": len(result.sources),
                        "sources": serialized_sources,
                        "metadata": metadata,
                    },
                )

        stream = current_runtime_stream.get()
        if stream is not None and serialized_sources:
            await stream.emit(
                "sources",
                sources=serialized_sources,
            )

        strategy_sources = tuple(
            StrategyKnowledgeSource(
                document_id=source.document_id,
                document_title=source.document_title,
                chunk_id=source.chunk_id,
                page_number=source.page_number,
                score=source.score,
                content_preview=source.content_preview,
            )
            for source in result.sources
        )
        return StrategyKnowledgeResult(
            content=result.content,
            query=query,
            sources=strategy_sources,
            metadata=metadata,
        )
