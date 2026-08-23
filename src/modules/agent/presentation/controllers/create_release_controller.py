from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import CreateReleaseInput
from modules.agent.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


def _release_payload(release):
    data = release_to_response(release).model_dump()
    data["provider_model_id"] = getattr(release, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(release, "fallback_provider_model_id", None)
    return data


class CreateReleaseController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body or {})
        change_kind = body.pop("change_kind", "change")
        if not body.get("version"):
            body["version"] = "auto"
        input_dto = CreateReleaseInput(**body)
        result = await self._use_case.execute(input_dto, change_kind=change_kind)
        return Response(status_code=201, body={"success": True, "data": _release_payload(result)})
