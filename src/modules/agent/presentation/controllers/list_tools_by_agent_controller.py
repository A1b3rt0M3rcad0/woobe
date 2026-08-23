from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos.tools_dtos import ListToolsByAgentInput
from modules.agent.presentation.controllers.list_tools_controller import render_tool
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListToolsByAgentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.path_params["agent_id"]
        input_dto = ListToolsByAgentInput(agent_id=agent_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [render_tool(tool) for tool in result]},
        )
