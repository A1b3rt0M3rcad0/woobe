from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AgentRunContextUseCase(Protocol):
    async def by_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> list[dict]: ...

    async def by_trace(
        self,
        *,
        trace_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> list[dict]: ...

    async def detail_by_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> dict: ...

    async def detail_by_trace(
        self,
        *,
        trace_id: UUID,
        user_id: UUID | None,
        control_plane_authorized: bool = False,
    ) -> dict: ...
