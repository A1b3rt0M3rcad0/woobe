from modules.agent.application.use_cases.tools_use_cases import ListToolsByAgentUseCase
from modules.agent.application.dtos.tools_dtos import ListToolsByAgentInput
from modules.agent.presentation.schemas import ToolResponse
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
            body={"success": True, "message": "ok", "data": [ToolResponse(**vars(r)).model_dump() for r in result]},
        )
