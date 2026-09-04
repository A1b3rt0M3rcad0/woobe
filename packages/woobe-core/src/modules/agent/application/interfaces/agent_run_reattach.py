from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol
from uuid import UUID


class AgentRunReattachOperations(Protocol):
    async def authorize(self, *, run_id: UUID, principal: object | None) -> None: ...

    async def active(
        self,
        *,
        session_id: UUID,
        principal: object | None,
    ) -> dict | None: ...

    def stream_sse(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> AsyncIterator[str]: ...

    async def cancel(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> dict: ...

    async def resolve_target_run(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
        preferred_run_id: UUID | None = None,
        created_after: datetime | None = None,
    ) -> dict | None: ...

    async def durable_target_state(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> dict: ...

    async def cancel_target_run(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID,
        agent_release_id: UUID,
    ) -> dict: ...
