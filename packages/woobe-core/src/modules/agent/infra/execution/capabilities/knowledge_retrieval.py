from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from modules.agent.application.interfaces.knowledge import (
    KnowledgeResult,
    KnowledgeSource,
)


KnowledgeRetrieveFn = Callable[[str], Awaitable[Any]]


def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(key)
    return getattr(source, key, None)


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
                document_id=_source_value(source, "document_id"),
                document_title=_source_value(source, "document_title"),
                chunk_id=_source_value(source, "chunk_id"),
                page_number=_source_value(source, "page_number"),
                score=_source_value(source, "score"),
                content_preview=_source_value(source, "content_preview"),
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
