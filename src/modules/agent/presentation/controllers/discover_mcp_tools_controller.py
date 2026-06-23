from modules.agent.application.mcp_discovery import (
    DiscoverMcpToolsUseCase,
    McpDiscoverInput,
)
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class DiscoverMcpToolsController(Controller):
    def __init__(self, use_case: DiscoverMcpToolsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = McpDiscoverInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
