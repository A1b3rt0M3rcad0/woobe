from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol
from uuid import UUID

from modules.network.application.dtos.observation import NetworkRunObservation

DisconnectCheck = Callable[[], Awaitable[bool]]


class NetworkRunReattachOperations(Protocol):
    async def authorize(
        self,
        *,
        run_id: UUID,
        principal: object | None,
    ) -> None: ...

    async def active(
        self,
        *,
        principal: object | None,
        network_session_id: UUID | None = None,
        network_id: UUID | None = None,
        environment: str | None = None,
    ) -> dict | None: ...

    async def wait_terminal(
        self,
        *,
        run_id: UUID,
        principal: object | None,
        timeout_seconds: float,
    ) -> NetworkRunObservation: ...

    def stream_sse(
        self,
        *,
        run_id: UUID,
        principal: object | None,
        is_disconnected: DisconnectCheck | None = None,
    ) -> AsyncIterator[str]: ...
