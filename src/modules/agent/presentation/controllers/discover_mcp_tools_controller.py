from modules.agent.application.dtos.mcp_discovery_dtos import McpDiscoverInput
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class DiscoverMcpToolsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = McpDiscoverInput(**request.body)
        result = await self._use_case.execute(input_dto)
        if result.error:
            return Response(status_code=502, body={"success": False, "message": result.error, "data": result.model_dump()})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})
