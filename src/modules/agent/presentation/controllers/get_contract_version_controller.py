from uuid import UUID
from modules.agent.application.use_cases.ai_use_cases import GetContractUseCase
from modules.agent.presentation.mappers import contract_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetContractVersionController(Controller):
    def __init__(self, use_case: GetContractUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        contract_id = request.path_params["contract_id"]
        result = await self._use_case.execute(UUID(contract_id))
        return Response(
            status_code=200,
            body={"success": True, "data": contract_to_response(result).model_dump()},
        )
