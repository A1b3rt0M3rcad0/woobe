from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

from modules.agent.application.dtos.runtime_dtos import SourceInfo


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
    query_mode: str = "conversation_context"
    history_turns: int = 3

    async def retrieve(self, *, query: str) -> KnowledgeRetrievalResult:
        if self.retrieve_fn is None or not query:
            return KnowledgeRetrievalResult(content=None)

        raw = await self.retrieve_fn(query)
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
        return KnowledgeRetrievalResult(
            content=content if isinstance(content, str) else None,
            sources=sources,
            metadata=metadata,
        )
