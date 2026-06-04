from modules.ai.service.use_cases import GetAgentByIdUseCase
from modules.ai.service.dtos import GetAgentInput
from modules.ai.presentation.mappers import agent_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetAgentController(Controller):
    def __init__(self, use_case: GetAgentByIdUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.path_params["agent_id"]
        input_dto = GetAgentInput(agent_id=agent_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": agent_to_response(result).model_dump()},
        )
