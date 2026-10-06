from modules.agent.application.dtos.imported_model_dtos import ResolveImportedModelInput
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)
from shared.presentation.interface.controller import Controller


class ResolveImportedModelController(Controller):
    def __init__(self, use_case: UseCase):
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = ResolveImportedModelInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS
            if input_dto.expected_model_id
            else OperationOutcome.CREATED,
            body={"success": True, "data": result.model_dump(mode="json")},
        )
