from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.execution_context import current_execution


KnowledgeRetrieveFn = Callable[[str], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalResult:
    """Normalized Knowledge result independent from the concrete retrieval strategy."""

    content: str | None
    sources: tuple[SourceInfo, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalCapability:
    """Runtime-governed Knowledge access exposed to Strategy Runtime."""

    retrieve_fn: KnowledgeRetrieveFn | None
    default_query: str | None = None

    async def retrieve(self, *, query: str | None = None) -> KnowledgeRetrievalResult:
        effective_query = query if query is not None else self.default_query
        if self.retrieve_fn is None or not effective_query:
            return KnowledgeRetrievalResult(content=None)

        raw = await self.retrieve_fn(effective_query)
        content = getattr(raw, "content", None)
        if content is None:
            content = getattr(raw, "context", None)

        raw_sources = getattr(raw, "sources", ()) or ()
        sources = tuple(
            source for source in raw_sources if isinstance(source, SourceInfo)
        )

        metadata: dict[str, Any] = {}
        metrics = getattr(raw, "metrics", None)
        if isinstance(metrics, Mapping):
            metadata.update(metrics)
        context = current_execution.get()
        if context is not None and isinstance(context.rag_metadata, dict):
            metadata = {**context.rag_metadata, **metadata}

        return KnowledgeRetrievalResult(
            content=content if isinstance(content, str) else None,
            sources=sources,
            metadata=metadata,
        )
