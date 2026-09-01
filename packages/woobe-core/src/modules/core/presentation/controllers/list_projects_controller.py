from modules.core.application.use_cases import ListProjectsUseCase
from modules.core.application.dtos import ListProjectsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListProjectsController(Controller):
    def __init__(self, use_case: ListProjectsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        workspace_id = request.query_params.get("workspace_id")
        input_dto = ListProjectsInput(workspace_id=workspace_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [r.model_dump() for r in result]},
        )
