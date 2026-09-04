from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.application.dtos.tools_dtos import UpdateToolInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class UpdateToolController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        tool_id = UUID(request.path_params["tool_id"])
        input_dto = UpdateToolInput(**request.body)
        result = await self._use_case.execute(tool_id, input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "updated", "data": result.model_dump()},
        )

