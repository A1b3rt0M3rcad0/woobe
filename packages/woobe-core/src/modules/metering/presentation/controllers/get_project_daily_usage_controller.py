from modules.metering.application.use_cases import GetProjectDailyUsageUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetProjectDailyUsageController(Controller):
    def __init__(self, use_case: GetProjectDailyUsageUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = request.path_params["project_id"]
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        result = await self._use_case.execute(project_id, limit=limit, offset=offset)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )

