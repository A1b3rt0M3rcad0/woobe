from __future__ import annotations

from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.network.application.interfaces.run_reattach import (
    NetworkRunReattachOperations,
)


class NetworkRunReattachController:
    def __init__(self, operations: NetworkRunReattachOperations) -> None:
        self._operations = operations

    @staticmethod
    def _principal(request: FastAPIRequest) -> object | None:
        return getattr(request.state, "principal", None)

    async def active(
        self,
        request: FastAPIRequest,
        network_session_id: UUID | None = None,
        network_id: UUID | None = None,
        environment: str | None = None,
    ) -> dict:
        data = await self._operations.active(
            principal=self._principal(request),
            network_session_id=network_session_id,
            network_id=network_id,
            environment=environment,
        )
        return {"success": True, "data": data}

    async def attach(
        self,
        run_id: UUID,
        request: FastAPIRequest,
    ) -> StreamingResponse:
        principal = self._principal(request)
        await self._operations.authorize(run_id=run_id, principal=principal)

        async def generate():
            async for chunk in self._operations.stream_sse(
                run_id=run_id,
                principal=principal,
                is_disconnected=request.is_disconnected,
            ):
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Network-Execution-ID": str(run_id),
            },
        )
