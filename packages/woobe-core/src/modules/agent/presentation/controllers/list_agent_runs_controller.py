from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.agent_run_listing import AgentRunListingUseCase
from shared.contracts.errors import AuthorizationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal


class ListAgentRunsController:
    def __init__(self, use_case: AgentRunListingUseCase) -> None:
        self._use_case = use_case

    @staticmethod
    def _actor(request: OperationRequest) -> tuple[UUID | None, bool]:
        principal = request.principal
        if isinstance(principal, AuthenticatedPrincipal):
            return principal.user_id, False
        if isinstance(principal, ControlPlanePrincipal):
            return None, True
        raise AuthorizationError("Control-plane authentication required")

    async def handle(self, request: OperationRequest) -> OperationResult:
        query = request.query_params
        project_id = UUID(str(query["project_id"]))
        agent_id = UUID(str(query["agent_id"]))
        raw_session_id = query.get("session_id")
        raw_environment = query.get("environment")
        raw_limit = query.get("limit", 100)
        try:
            limit = max(1, min(int(raw_limit), 200))
        except (TypeError, ValueError):
            limit = 100

        user_id, control_plane_authorized = self._actor(request)
        data = await self._use_case.execute(
            user_id=user_id,
            project_id=project_id,
            control_plane_authorized=control_plane_authorized,
            agent_id=agent_id,
            session_id=UUID(str(raw_session_id)) if raw_session_id else None,
            environment=str(raw_environment) if raw_environment else None,
            limit=limit,
        )
        return OperationResult(outcome=OperationOutcome.SUCCESS, body={"success": True, "data": data})

