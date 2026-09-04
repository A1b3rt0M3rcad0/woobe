from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import list_contracts_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


class ListContractVersionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        agent_id = request.path_params["agent_id"]
        result = await self._use_case.execute(agent_id)
        items = [list_contracts_to_response(c).model_dump() for c in result]
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "data": items},
        )

