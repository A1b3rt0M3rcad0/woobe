from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AgentRunContextOperations(Protocol):
    async def list_model_invocations(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> list[dict]: ...

    async def list_model_invocations_by_trace(
        self,
        *,
        trace_id: UUID,
        principal: object | None,
    ) -> list[dict]: ...
