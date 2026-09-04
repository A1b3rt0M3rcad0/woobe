from modules.identity.application.use_cases import GetCurrentUserUseCase
from modules.identity.application.dtos import GetCurrentUserInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class GetCurrentUserController(Controller):
    def __init__(self, use_case: GetCurrentUserUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        result = await self._use_case.execute(GetCurrentUserInput())
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )

