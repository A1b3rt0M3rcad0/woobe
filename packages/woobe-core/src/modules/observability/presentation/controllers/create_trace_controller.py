from modules.observability.application.use_cases import CreateTraceUseCase
from modules.observability.application.dtos import CreateTraceInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class CreateTraceController(Controller):
    def __init__(self, use_case: CreateTraceUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = CreateTraceInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": {"trace_id": str(result.trace_id)}},
        )

