from dataclasses import asdict

from modules.tools.presentation.schemas import ToolResponse
from modules.tools.application.use_cases import ListToolsUseCase
from modules.tools.application.dtos import ListToolsInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListToolsController(Controller):
    def __init__(self, use_case: ListToolsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = request.query_params.get("project_id")
        input_dto = ListToolsInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": [ToolResponse(**asdict(r)).model_dump() for r in result]},
        )
