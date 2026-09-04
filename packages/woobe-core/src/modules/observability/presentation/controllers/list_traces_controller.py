from modules.observability.application.use_cases import ListTracesUseCase
from modules.observability.application.dtos import ListTracesInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListTracesController(Controller):
    def __init__(self, use_case: ListTracesUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = request.query_params.get("project_id")
        agent_id = request.query_params.get("agent_id")
        session_id = request.query_params.get("session_id")
        network_id = request.query_params.get("network_id")
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        input_dto = ListTracesInput(
            project_id=project_id,
            agent_id=agent_id,
            session_id=session_id,
            network_id=network_id,
            limit=limit,
            offset=offset,
        )
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )

