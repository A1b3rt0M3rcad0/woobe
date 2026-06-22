from uuid import UUID

from modules.agent.application.dtos import PromoteReleaseInput
from modules.agent.application.use_cases import PromoteReleaseUseCase
from modules.agent.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class PromoteReleaseController(Controller):
    def __init__(self, use_case: PromoteReleaseUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        release_id = UUID(request.path_params["release_id"])
        body = request.body or {}
        input_dto = PromoteReleaseInput(**body)
        result = await self._use_case.execute(
            agent_id,
            release_id,
            input_dto,
            target_status=body.get("target_status", "production"),
            copy_snapshot=bool(body.get("copy_snapshot", False)),
            change_kind=body.get("change_kind", "change"),
        )
        return Response(status_code=200, body={"success": True, "data": release_to_response(result).model_dump()})
