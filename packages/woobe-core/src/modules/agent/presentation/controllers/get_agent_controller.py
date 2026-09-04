from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import GetAgentInput
from modules.agent.presentation.mappers import agent_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


def _agent_payload(agent):
    data = agent_to_response(agent).model_dump()
    data["provider_model_id"] = getattr(agent, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(agent, "fallback_provider_model_id", None)
    return data


class GetAgentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        agent_id = request.path_params["agent_id"]
        input_dto = GetAgentInput(agent_id=agent_id)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": _agent_payload(result)},
        )

