from modules.observability.application.use_cases import GetTraceUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.infra.errors import NotFoundError


class GetTraceController(Controller):
    def __init__(self, use_case: GetTraceUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        trace_id = request.path_params["trace_id"]
        try:
            result = await self._use_case.execute(trace_id)
        except NotFoundError as e:
            return OperationResult(outcome=OperationOutcome.NOT_FOUND, body={"success": False, "message": str(e), "data": None})
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )

