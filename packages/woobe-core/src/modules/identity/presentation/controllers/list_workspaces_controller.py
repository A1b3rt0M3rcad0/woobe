from modules.identity.application.use_cases import ListWorkspacesUseCase
from modules.identity.application.dtos import ListWorkspacesInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListWorkspacesController(Controller):
    def __init__(self, use_case: ListWorkspacesUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        result = await self._use_case.execute(ListWorkspacesInput())
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )

