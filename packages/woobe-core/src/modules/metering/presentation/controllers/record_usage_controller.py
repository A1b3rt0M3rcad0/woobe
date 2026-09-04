from modules.metering.application.use_cases import RecordUsageUseCase
from modules.metering.application.dtos import RecordUsageInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class RecordUsageController(Controller):
    def __init__(self, use_case: RecordUsageUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = RecordUsageInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": {"event_id": str(result.event_id)}},
        )

