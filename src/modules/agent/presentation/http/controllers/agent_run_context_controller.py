from __future__ import annotations

from uuid import UUID

from fastapi import Request as FastAPIRequest

from modules.agent.application.interfaces.agent_run_context import AgentRunContextOperations


class AgentRunContextController:
    def __init__(self, operations: AgentRunContextOperations) -> None:
        self._operations = operations

    @staticmethod
    def _principal(request: FastAPIRequest) -> object | None:
        return getattr(request.state, "principal", None)

    async def list_model_invocations(
        self,
        run_id: UUID,
        request: FastAPIRequest,
    ) -> dict:
        data = await self._operations.list_model_invocations(
            run_id=run_id,
            principal=self._principal(request),
        )
        return {"success": True, "data": data}

    async def list_model_invocations_by_trace(
        self,
        trace_id: UUID,
        request: FastAPIRequest,
    ) -> dict:
        data = await self._operations.list_model_invocations_by_trace(
            trace_id=trace_id,
            principal=self._principal(request),
        )
        return {"success": True, "data": data}
