from modules.agent.application.dtos.destination_binding_dtos import (
    InspectDestinationBindingsInput,
)
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.contracts import OperationRequest, OperationResult


class InspectDestinationBindingsController:
    def __init__(self, use_case: UseCase):
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        data = await self._use_case.execute(
            InspectDestinationBindingsInput.model_validate(request.body)
        )
        return OperationResult(body={"success": True, "data": data})
