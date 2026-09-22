from __future__ import annotations

from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from modules.agent.domain.context import ContextSourceType


class ContextSummarySelection(BaseModel):
    """Aggregate source selection inspected before creating or reusing a summary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: ContextSourceType
    source_refs: tuple[str, ...]
    source_hash: str
    raw_units: int
    candidate_count: int
    preserve_recent_messages: int = 0


class ContextSummaryResult(BaseModel):
    """Serializable semantic-summary transformation produced by Context Runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary_ref: str
    source: ContextSourceType
    source_refs: tuple[str, ...]
    source_hash: str
    content: str
    raw_units: int
    materialized_units: int
    preserve_recent_messages: int = 0
    model_invocation_id: UUID | None = None
    provider: str | None = None
    model: str | None = None


class ContextSummary(Protocol):
    """Semantic-summary capability owned by Context Manager Runtime."""

    def inspect(
        self,
        source: ContextSourceType,
        *,
        preserve_recent_messages: int = 0,
    ) -> ContextSummarySelection: ...

    async def create(
        self,
        source: ContextSourceType,
        *,
        target_units: int,
        preserve_recent_messages: int = 0,
    ) -> ContextSummaryResult: ...

    async def refresh(
        self,
        summary: ContextSummaryResult,
        *,
        target_units: int,
        preserve_recent_messages: int | None = None,
    ) -> ContextSummaryResult: ...

    def apply(self, summary: ContextSummaryResult) -> None: ...
