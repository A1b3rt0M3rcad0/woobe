from uuid import UUID

from modules.agent.application.use_cases.tools_use_cases import DeleteToolUseCase
from modules.agent.application.dtos.tools_dtos import DeleteToolInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class DeleteToolController(Controller):
    def __init__(self, use_case: DeleteToolUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        tool_id = UUID(request.path_params["tool_id"])
        input_dto = DeleteToolInput(tool_id=tool_id)
        await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "deleted", "data": None},
        )
