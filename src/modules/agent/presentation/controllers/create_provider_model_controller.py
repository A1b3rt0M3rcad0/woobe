from modules.agent.application.dtos import CreateProviderModelInput
from modules.agent.application.use_cases import CreateProviderModelUseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class CreateProviderModelController(Controller):
    def __init__(self, use_case: CreateProviderModelUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateProviderModelInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": result.model_dump()},
        )
