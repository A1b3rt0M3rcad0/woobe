from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID


class AgentRunReattachGateway(Protocol):
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
