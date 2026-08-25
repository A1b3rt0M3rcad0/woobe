from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import list_releases_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


def _release_list_payload(release):
    data = list_releases_to_response(release).model_dump()
    data["project_id"] = release.project_id
    data["agent_id"] = release.agent_id
    data["snapshot_kind"] = getattr(release, "snapshot_kind", None)
    data["session_mode"] = getattr(release, "session_mode", None)
    data["provider_model_id"] = getattr(release, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(release, "fallback_provider_model_id", None)
    data["knowledge_version_id"] = getattr(release, "knowledge_version_id", None)
    data["updated_at"] = getattr(release, "updated_at", None)
    return data


class ListReleasesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.path_params["agent_id"]
        result = await self._use_case.execute(agent_id)
        items = [_release_list_payload(release) for release in result]
        return Response(
            status_code=200,
            body={"success": True, "data": items},
        )
