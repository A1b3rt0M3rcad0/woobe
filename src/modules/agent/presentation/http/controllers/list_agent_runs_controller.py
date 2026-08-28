from __future__ import annotations

from uuid import UUID

from modules.agent.application.use_cases.list_agent_runs import ListAgentRunsUseCase
from shared.contracts.errors import AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.security.principal import AuthenticatedPrincipal


class ListAgentRunsController:
    def __init__(self, use_case: ListAgentRunsUseCase) -> None:
        self._use_case = use_case

    @staticmethod
    def _user_id(request: Request) -> UUID:
        principal = request.principal
        if not isinstance(principal, AuthenticatedPrincipal):
            raise AuthorizationError("Control-plane authentication required")
        return principal.user_id

    async def handle(self, request: Request) -> Response:
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

        data = await self._use_case.execute(
            user_id=self._user_id(request),
            project_id=project_id,
            agent_id=agent_id,
            session_id=UUID(str(raw_session_id)) if raw_session_id else None,
            environment=str(raw_environment) if raw_environment else None,
            limit=limit,
        )
        return Response(status_code=200, body={"success": True, "data": data})
