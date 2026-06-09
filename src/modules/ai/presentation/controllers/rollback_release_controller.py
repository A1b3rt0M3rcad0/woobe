from uuid import UUID
from modules.ai.service.use_cases import RollbackReleaseUseCase
from modules.ai.service.dtos import RollbackReleaseInput
from modules.ai.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class RollbackReleaseController(Controller):
    def __init__(self, use_case: RollbackReleaseUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        release_id = request.path_params["release_id"]
        input_dto = RollbackReleaseInput(**request.body)
        result = await self._use_case.execute(UUID(release_id), input_dto)
        return Response(
            status_code=200,
            body={"success": True, "data": release_to_response(result).model_dump()},
        )
