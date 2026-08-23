from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID
from modules.agent.application.dtos import UpdateContractInput
from modules.agent.presentation.mappers import contract_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class UpdateContractVersionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        contract_id = request.path_params["contract_id"]
        input_dto = UpdateContractInput(**request.body)
        result = await self._use_case.execute(UUID(contract_id), input_dto)
        return Response(
            status_code=200,
            body={"success": True, "data": contract_to_response(result).model_dump()},
        )
