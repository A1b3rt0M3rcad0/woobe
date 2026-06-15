from uuid import UUID

from modules.agent.application.use_cases.runtime_use_cases import ListAgentSessionsUseCase
from modules.agent.application.dtos import ListAgentSessionsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListAgentSessionsController(Controller):
    def __init__(self, use_case: ListAgentSessionsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        project_id = UUID(request.query_params["project_id"])
        input_dto = ListAgentSessionsInput(project_id=project_id, agent_id=agent_id)
        try:
            result = await self._use_case.execute(input_dto)
        except Exception as e:
            return Response(
                status_code=400,
                body={"success": False, "message": str(e), "data": None},
            )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )
