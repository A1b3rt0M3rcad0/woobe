from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import CreateModelConfigInput
from modules.agent.presentation.mappers import model_config_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateModelConfigController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateModelConfigInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "data": model_config_to_response(result).model_dump()},
        )
