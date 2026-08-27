from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.agent_run_repository import AgentRunRepository
from modules.agent.application.interfaces.project_access_repository import ProjectAccessRepository
from shared.contracts.errors import NotFoundError


class ReadAgentRunContextUseCase:
    def __init__(
        self,
        run_repository: AgentRunRepository,
        project_access_repository: ProjectAccessRepository,
    ) -> None:
        self._runs = run_repository
        self._project_access = project_access_repository

    async def by_run(
        self,
        *,
        run_id: UUID,
        user_id: UUID,
    ) -> list[dict]:
        run = await self._runs.get_by_id(run_id)
        if run is None:
            raise NotFoundError("Agent Run not found")
        await self._project_access.require_user_access(
            user_id=user_id,
            project_id=run.project_id,
        )
        return await self._runs.list_model_invocations(run.id)

    async def by_trace(
        self,
        *,
        trace_id: UUID,
        user_id: UUID,
    ) -> list[dict]:
        run = await self._runs.get_by_trace_id(trace_id)
        if run is None:
            raise NotFoundError("Agent Run not found for Trace")
        await self._project_access.require_user_access(
            user_id=user_id,
            project_id=run.project_id,
        )
        return await self._runs.list_model_invocations(run.id)
