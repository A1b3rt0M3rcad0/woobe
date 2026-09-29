from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from modules.agent.application.interfaces.knowledge import (
    KnowledgeResult,
    KnowledgeSource,
)


KnowledgeRetrieveFn = Callable[[str], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalCapability:
    """Runtime-governed retrieval mechanism available to Knowledge Strategies.

    Query construction and retrieval policy intentionally do not live here. They
    belong to the selected Knowledge Strategy.
    """

    retrieve_fn: KnowledgeRetrieveFn | None

    @property
    def available(self) -> bool:
        return self.retrieve_fn is not None

    async def retrieve(self, *, query: str) -> KnowledgeResult:
        normalized_query = query.strip()
        if self.retrieve_fn is None or not normalized_query:
            return KnowledgeResult(content=None, query=normalized_query or None)

        raw = await self.retrieve_fn(normalized_query)
        content = getattr(raw, "content", None)
        if content is None:
            content = getattr(raw, "context", None)

        raw_sources = getattr(raw, "sources", ()) or ()
        sources = tuple(
            KnowledgeSource(
                document_id=getattr(source, "document_id", None),
                document_title=getattr(source, "document_title", None),
                chunk_id=getattr(source, "chunk_id", None),
                page_number=getattr(source, "page_number", None),
                score=getattr(source, "score", None),
                content_preview=getattr(source, "content_preview", None),
            )
            for source in raw_sources
        )

        metadata: dict[str, Any] = {}
        raw_metadata = getattr(raw, "metadata", None)
        if isinstance(raw_metadata, Mapping):
            metadata.update(raw_metadata)
        metrics = getattr(raw, "metrics", None)
        if isinstance(metrics, Mapping):
            metadata.update(metrics)

        return KnowledgeResult(
            content=content if isinstance(content, str) else None,
            query=normalized_query,
            sources=sources,
            metadata=metadata,
        )
