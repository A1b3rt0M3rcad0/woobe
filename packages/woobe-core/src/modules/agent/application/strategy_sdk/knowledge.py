from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from modules.agent.application.strategy_sdk.model import StrategyPhase


@dataclass(frozen=True, slots=True)
class StrategyKnowledgeQueryPolicy:
    """Frozen retrieval-query policy resolved by the Runtime for the Strategy."""

    mode: str = "conversation_context"
    history_turns: int = 3

    def __post_init__(self) -> None:
        if self.mode not in {"current_message", "conversation_context"}:
            raise ValueError(f"Unsupported Knowledge query mode: {self.mode}")
        if self.history_turns <= 0:
            raise ValueError("Knowledge history_turns must be positive")


@dataclass(frozen=True, slots=True)
class StrategyKnowledgeSource:
    """Framework-neutral Knowledge source exposed to Execution Strategies."""

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
class StrategyKnowledgeResult:
    """Knowledge retrieval result exposed to Execution Strategies."""

    content: str | None
    query: str | None = None
    sources: tuple[StrategyKnowledgeSource, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.content)


class StrategyKnowledge(Protocol):
    """Knowledge operations available to an Execution Strategy."""

    @property
    def query_policy(self) -> StrategyKnowledgeQueryPolicy: ...

    async def retrieve(
        self,
        *,
        query: str,
        phase: StrategyPhase | None = None,
    ) -> StrategyKnowledgeResult: ...
