from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import UpdateAgentInput
from modules.agent.presentation.mappers import agent_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


def _agent_payload(agent):
    data = agent_to_response(agent).model_dump()
    data["provider_model_id"] = getattr(agent, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(agent, "fallback_provider_model_id", None)
    return data


class UpdateAgentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.path_params["agent_id"]
        raw = {k: v for k, v in request.body.items() if v is not None}
        input_dto = UpdateAgentInput(**raw)
        result = await self._use_case.execute(agent_id, input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": _agent_payload(result)},
        )
