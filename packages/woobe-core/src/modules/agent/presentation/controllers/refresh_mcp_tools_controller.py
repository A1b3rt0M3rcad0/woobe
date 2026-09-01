from modules.agent.application.dtos.mcp_tool_refresh_dtos import RefreshMcpProviderToolsInput
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class RefreshMcpToolsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            result = await self._use_case.execute(RefreshMcpProviderToolsInput(**request.body))
        except ValueError as exc:
            return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})
