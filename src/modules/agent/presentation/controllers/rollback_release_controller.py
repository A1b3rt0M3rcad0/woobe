from uuid import UUID

from modules.agent.application.dtos import RollbackReleaseInput
from modules.agent.application.use_cases.ai_use_cases import RollbackReleaseUseCase
from modules.agent.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


def _release_payload(release):
    data = release_to_response(release).model_dump()
    data["provider_model_id"] = getattr(release, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(release, "fallback_provider_model_id", None)
    return data


class RollbackReleaseController(Controller):
    def __init__(self, use_case: RollbackReleaseUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        release_id = UUID(request.path_params["release_id"])
        input_dto = RollbackReleaseInput(**request.body)
        result = await self._use_case.execute(agent_id, release_id, input_dto)
        return Response(
            status_code=200,
            body={"success": True, "data": _release_payload(result)},
        )
