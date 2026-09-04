from modules.agent.application.dtos import CreateSessionInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class CreateSessionController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = CreateSessionInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": result.model_dump()},
        )

