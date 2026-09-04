from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID
from modules.agent.application.dtos import UpdateContractInput
from modules.agent.presentation.mappers import contract_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class UpdateContractVersionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        contract_id = request.path_params["contract_id"]
        input_dto = UpdateContractInput(**request.body)
        result = await self._use_case.execute(UUID(contract_id), input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "data": contract_to_response(result).model_dump()},
        )

