from dataclasses import asdict

from modules.tools.presentation.schemas import ToolResponse
from modules.tools.application.use_cases import ListToolsByAgentUseCase
from modules.tools.application.dtos import ListToolsByAgentInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListToolsByAgentController(Controller):
    def __init__(self, use_case: ListToolsByAgentUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.path_params["agent_id"]
        input_dto = ListToolsByAgentInput(agent_id=agent_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [ToolResponse(**asdict(r)).model_dump() for r in result]},
        )
