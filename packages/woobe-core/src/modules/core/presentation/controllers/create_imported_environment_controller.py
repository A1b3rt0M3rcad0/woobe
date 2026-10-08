from modules.core.application.dtos.imported_environment_dtos import (
    CreateImportedEnvironmentInput,
)
from shared.presentation.contracts import OperationOutcome, OperationResult


class CreateImportedEnvironmentController:
    def __init__(self, use_case):
        self._use_case = use_case

    async def handle(self, request):
        result = await self._use_case.execute(
            CreateImportedEnvironmentInput.model_validate(request.body)
        )
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": result},
        )
