from modules.agent.application.use_cases.ai_use_cases import CreateReleaseTestUseCase
from modules.agent.application.dtos import CreateReleaseTestInput
from modules.agent.presentation.mappers import release_test_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateReleaseTestController(Controller):
    def __init__(self, use_case: CreateReleaseTestUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateReleaseTestInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "data": release_test_to_response(result).model_dump()},
        )
