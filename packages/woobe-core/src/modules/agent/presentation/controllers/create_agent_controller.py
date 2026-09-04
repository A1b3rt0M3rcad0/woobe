from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import CreateAgentInput
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


class CreateAgentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        input_dto = CreateAgentInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.CREATED,
            body={"success": True, "message": "created", "data": _agent_payload(result)},
        )

