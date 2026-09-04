from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.application.dtos import UpdateProviderModelInput
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


class UpdateProviderModelController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        provider_model_id = UUID(request.path_params["provider_model_id"])
        input_dto = UpdateProviderModelInput(**request.body)
        result = await self._use_case.execute(provider_model_id, input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "updated", "data": result.model_dump()},
        )

