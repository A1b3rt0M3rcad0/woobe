from __future__ import annotations

from modules.core.application.dtos.project_runs import ProjectRunsQuery
from modules.core.application.use_cases.get_project_runs import GetProjectRunsUseCase
from shared.presentation.contracts import OperationOutcome, OperationRequest, OperationResult
from shared.presentation.interface.controller import Controller


class GetProjectRunsController(Controller):
    def __init__(self, use_case: GetProjectRunsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        query = ProjectRunsQuery.model_validate(
            {
                "project_id": request.path_params["project_id"],
                "network_id": request.query_params.get("network_id"),
                "limit": request.query_params.get("limit", 100),
            }
        )
        result = await self._use_case.execute(query)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": result},
            metadata={
                "Cache-Control": "private, max-age=2",
                "Vary": "Authorization",
            },
        )
