from modules.core.application.use_cases import GetProjectByIdUseCase
from modules.core.application.dtos import GetProjectInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetProjectController(Controller):
    def __init__(self, use_case: GetProjectByIdUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = request.path_params["project_id"]
        input_dto = GetProjectInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )

