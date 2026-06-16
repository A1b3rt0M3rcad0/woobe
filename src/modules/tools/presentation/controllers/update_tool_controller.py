from uuid import UUID

from modules.tools.application.use_cases import UpdateToolUseCase
from modules.tools.application.dtos import UpdateToolInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class UpdateToolController(Controller):
    def __init__(self, use_case: UpdateToolUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        tool_id = UUID(request.path_params["tool_id"])
        input_dto = UpdateToolInput(**request.body)
        result = await self._use_case.execute(tool_id, input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "updated", "data": result.model_dump()},
        )
