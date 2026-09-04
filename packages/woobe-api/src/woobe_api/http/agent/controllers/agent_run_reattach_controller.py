from __future__ import annotations

from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.agent.entrypoint import (
    AgentRunReattachOperations,
)


class AgentRunReattachController:
    def __init__(self, operations: AgentRunReattachOperations) -> None:
        self._operations = operations

    @staticmethod
    def _principal(request: FastAPIRequest) -> object | None:
        return getattr(request.state, "principal", None)

    async def active(
        self,
        request: FastAPIRequest,
        session_id: UUID,
    ) -> dict:
        data = await self._operations.active(
            session_id=session_id,
            principal=self._principal(request),
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
            ):
                if await request.is_disconnected():
                    return
                yield chunk

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Woobe-Run-ID": str(run_id),
            },
        )

    async def cancel(
        self,
        run_id: UUID,
        request: FastAPIRequest,
    ) -> dict:
        data = await self._operations.cancel(
            run_id=run_id,
            principal=self._principal(request),
        )
        return {"success": True, "data": data}

