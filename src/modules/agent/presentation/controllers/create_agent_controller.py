from modules.agent.application.use_cases.ai_use_cases import CreateAgentUseCase
from modules.agent.application.dtos.ai_dtos import CreateAgentInput
from modules.agent.presentation.mappers import agent_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateAgentController(Controller):
    def __init__(self, use_case: CreateAgentUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateAgentInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": agent_to_response(result).model_dump()},
        )
