from modules.ai.service.use_cases import CreateContractUseCase
from modules.ai.service.dtos import CreateContractInput
from modules.ai.presentation.mappers import contract_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateContractVersionController(Controller):
    def __init__(self, use_case: CreateContractUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateContractInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "data": contract_to_response(result).model_dump()},
        )
