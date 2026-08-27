from __future__ import annotations

from uuid import UUID

from fastapi import Request as FastAPIRequest

from modules.agent.infra.execution.agent_run_context_service import AgentRunContextReadService


class AgentRunContextController:
    def __init__(self, service: AgentRunContextReadService) -> None:
        self._service = service

    async def list_model_invocations(
        self,
        run_id: UUID,
        request: FastAPIRequest,
    ) -> dict:
        data = await self._service.list_model_invocations(
            run_id=run_id,
            principal=getattr(request.state, "principal", None),
        )
        return {"success": True, "data": data}
