from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class KnowledgeMessage(Protocol):
    """Minimal conversation message surface required by Knowledge algorithms."""

    role: Any
    content: Any


class KnowledgeConversation(Protocol):
    """Read-only conversation surface available to Knowledge Strategies."""

    @property
    def current_user_message(self) -> KnowledgeMessage | None: ...

    @property
    def history(self) -> tuple[KnowledgeMessage, ...]: ...


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    """Framework-neutral provenance returned by Knowledge algorithms."""

    document_id: str | None = None
    document_title: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    score: float | None = None
    content_preview: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "chunk_id": self.chunk_id,
            "page_number": self.page_number,
            "score": self.score,
            "content_preview": self.content_preview,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeRequest:
    """Immutable input presented to one Knowledge Strategy invocation."""

    conversation: KnowledgeConversation
    runtime_config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeResult:
    """Framework-neutral Knowledge result returned by a Knowledge Strategy."""

    content: str | None
    query: str | None = None
    sources: tuple[KnowledgeSource, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.content)


@runtime_checkable
class KnowledgeCapabilities(Protocol):
    """Runtime-owned mechanisms a Knowledge Strategy may compose."""

    @property
    def available(self) -> bool: ...

    async def retrieve(
        self,
        *,
        query: str,
    ) -> KnowledgeResult: ...


@runtime_checkable
class KnowledgeStrategy(Protocol):
    """Programmable algorithm that owns Knowledge retrieval behavior."""

    name: str

    async def retrieve(
        self,
        request: KnowledgeRequest,
        capabilities: KnowledgeCapabilities,
    ) -> KnowledgeResult: ...


@runtime_checkable
class KnowledgeStrategyResolver(Protocol):
    """Resolve a configured Knowledge Strategy without exposing its registry."""

    def resolve(self, name: str) -> KnowledgeStrategy: ...


__all__ = [
    "KnowledgeCapabilities",
    "KnowledgeConversation",
    "KnowledgeMessage",
    "KnowledgeRequest",
    "KnowledgeSource",
    "KnowledgeResult",
    "KnowledgeStrategy",
    "KnowledgeStrategyResolver",
]
