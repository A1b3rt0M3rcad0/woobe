from uuid import UUID

from modules.ai.service.dtos import PromoteReleaseInput
from modules.ai.service.use_cases import PromoteReleaseUseCase
from modules.ai.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class PromoteReleaseController(Controller):
    def __init__(self, use_case: PromoteReleaseUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        release_id = UUID(request.path_params["release_id"])
        input_dto = PromoteReleaseInput(**request.body)
        result = await self._use_case.execute(agent_id, release_id, input_dto)
        return Response(
            status_code=200,
            body={"success": True, "data": release_to_response(result).model_dump()},
        )
