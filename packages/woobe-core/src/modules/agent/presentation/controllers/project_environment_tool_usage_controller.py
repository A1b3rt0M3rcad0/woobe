from uuid import UUID

from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)
from shared.presentation.interface.controller import Controller


class ProjectEnvironmentToolUsageController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = UUID(str(request.path_params["project_id"]))
        usage = await self._use_case.execute(project_id)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": usage},
        )
