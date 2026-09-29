from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from modules.agent.application.dtos.runtime_dtos import SourceInfo


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
class KnowledgeRequest:
    """Immutable input presented to one Knowledge Strategy invocation."""

    conversation: KnowledgeConversation
    runtime_config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeResult:
    """Framework-neutral Knowledge result returned by a Knowledge Strategy."""

    content: str | None
    query: str | None = None
    sources: tuple[SourceInfo, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.content)


@runtime_checkable
class KnowledgeCapabilities(Protocol):
    """Runtime-owned mechanisms a Knowledge Strategy may compose."""

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
    "KnowledgeResult",
    "KnowledgeStrategy",
    "KnowledgeStrategyResolver",
]
