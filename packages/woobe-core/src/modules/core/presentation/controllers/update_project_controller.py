from modules.core.application.use_cases import UpdateProjectUseCase
from modules.core.application.dtos import UpdateProjectInput
from modules.core.presentation.schemas import ProjectResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class UpdateProjectController(Controller):
    def __init__(self, use_case: UpdateProjectUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        body = dict(request.body)
        body["project_id"] = request.path_params["project_id"]
        input_dto = UpdateProjectInput(**body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": ProjectResponse(**result.model_dump()).model_dump()},
        )

