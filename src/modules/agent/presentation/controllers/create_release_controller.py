from modules.agent.application.dtos import CreateReleaseInput
from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase
from modules.agent.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateReleaseController(Controller):
    def __init__(self, use_case: AutoCreateReleaseUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateReleaseInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "data": release_to_response(result).model_dump()},
        )
