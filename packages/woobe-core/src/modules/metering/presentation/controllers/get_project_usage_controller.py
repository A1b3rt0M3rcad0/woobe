from __future__ import annotations

from modules.metering.application.dtos.project_usage import ProjectUsageQuery
from modules.metering.application.use_cases.get_project_usage import GetProjectUsageUseCase
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


class GetProjectUsageController(Controller):
    def __init__(self, use_case: GetProjectUsageUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        allowed = {
            "from",
            "to",
            "bucket",
            "environment",
            "operation",
            "network_id",
            "agent_id",
            "provider_model_id",
            "release_id",
            "group_by",
            "top_limit",
        }
        query = ProjectUsageQuery.model_validate(
            {
                "project_id": request.path_params["project_id"],
                **{
                    key: value
                    for key, value in request.query_params.items()
                    if key in allowed
                },
            }
        )
        result = await self._use_case.execute(query)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": result.model_dump(by_alias=True, mode="json"),
            },
            metadata={
                "Cache-Control": "private, max-age=15",
                "Vary": "Authorization",
            },
        )

