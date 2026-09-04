from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import ListAgentsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListAgentsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = request.query_params.get("project_id")
        input_dto = ListAgentsInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )

