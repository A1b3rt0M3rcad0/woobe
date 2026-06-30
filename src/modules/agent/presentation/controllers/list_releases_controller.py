from modules.agent.application.use_cases.ai_use_cases import ListReleasesUseCase
from modules.agent.presentation.mappers import list_releases_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


def _release_list_payload(release):
    data = list_releases_to_response(release).model_dump()
    data["provider_model_id"] = getattr(release, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(release, "fallback_provider_model_id", None)
    return data


class ListReleasesController(Controller):
    def __init__(self, use_case: ListReleasesUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.path_params["agent_id"]
        result = await self._use_case.execute(agent_id)
        items = [_release_list_payload(r) for r in result]
        return Response(
            status_code=200,
            body={"success": True, "data": items},
        )
