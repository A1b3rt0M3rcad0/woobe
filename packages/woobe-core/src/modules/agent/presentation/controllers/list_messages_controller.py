from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import ListMessagesInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.contracts.errors import NotFoundError


class ListMessagesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        session_id = request.path_params["session_id"]
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", 100))
        input_dto = ListMessagesInput(session_id=session_id, offset=offset, limit=limit)
        try:
            result = await self._use_case.execute(input_dto)
        except NotFoundError as e:
            return OperationResult(outcome=OperationOutcome.NOT_FOUND, body={"success": False, "message": str(e), "data": None})
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )

