from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.application.dtos import PromoteReleaseInput
from modules.agent.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


def _release_payload(release):
    data = release_to_response(release).model_dump()
    data["provider_model_id"] = getattr(release, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(release, "fallback_provider_model_id", None)
    return data


class PromoteReleaseController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        release_id = UUID(request.path_params["release_id"])
        body = request.body or {}
        input_dto = PromoteReleaseInput(**body)
        object.__setattr__(input_dto, "release_notes", body.get("release_notes"))
        object.__setattr__(input_dto, "change_description", body.get("change_description"))
        result = await self._use_case.execute(
            agent_id,
            release_id,
            input_dto,
            target_status=body.get("target_status", "production"),
            copy_snapshot=bool(body.get("copy_snapshot", False)),
            change_kind=body.get("change_kind", "change"),
        )
        return Response(status_code=200, body={"success": True, "data": _release_payload(result)})
