from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class AgentInvocationArtifact:
    invocation_id: UUID
    project_id: UUID
    agent_id: UUID
    session_id: UUID | None
    release_id: UUID | None
    parent_run_id: UUID | None
    trace_id: UUID | None
    network_execution_id: UUID
    environment: str
    status: str
    input_message: str
    output_message: str | None
    execution_snapshot: dict[str, Any]
    usage: dict[str, Any] | None
    result: dict[str, Any]
    failure: dict[str, Any] | None
    diagnostics: dict[str, Any] | None
    llm_calls: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    parsed_output: Any
    output_parse_error: str | None
    started_at: datetime
    completed_at: datetime


class AgentInvocationArtifactMaterializer(Protocol):
    """Outer adapter seam for Agent-owned artifacts created by a Network Run.

    The caller supplies the active SQLAlchemy session so Agent and Network
    persistence remain part of the same finalization transaction without making
    the Network bounded context import Agent infrastructure.
    """

    async def materialize(
        self,
        session: AsyncSession,
        artifact: AgentInvocationArtifact,
    ) -> None: ...
