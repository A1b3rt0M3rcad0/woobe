from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


class GetToolUsageImpactController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        tool_id = UUID(request.path_params["tool_id"])
        impact = await self._use_case.execute(tool_id)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "ok",
                "data": impact.model_dump(mode="json"),
            },
        )

