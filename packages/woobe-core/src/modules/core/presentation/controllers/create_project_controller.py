from modules.core.application.use_cases import CreateProjectUseCase
from modules.core.application.dtos import CreateProjectInput
from modules.core.presentation.schemas import ProjectResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class CreateProjectController(Controller):
    def __init__(self, use_case: CreateProjectUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = CreateProjectInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": ProjectResponse(**result.model_dump()).model_dump()},
        )

