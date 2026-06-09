from uuid import UUID
from modules.ai.service.use_cases import GetReleaseUseCase
from modules.ai.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetReleaseController(Controller):
    def __init__(self, use_case: GetReleaseUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        release_id = request.path_params["release_id"]
        result = await self._use_case.execute(UUID(release_id))
        return Response(
            status_code=200,
            body={"success": True, "data": release_to_response(result).model_dump()},
        )
