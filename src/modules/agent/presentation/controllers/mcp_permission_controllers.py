from modules.agent.application.mcp_permissions import (
    BulkUpdateMcpToolPermissionsInput,
    BulkUpdateMcpToolPermissionsUseCase,
    UpdateMcpToolPermissionsInput,
    UpdateMcpToolPermissionsUseCase,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class UpdateMcpPermissionsController(Controller):
    def __init__(self, use_case: UpdateMcpToolPermissionsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            result = await self._use_case.execute(UpdateMcpToolPermissionsInput(**request.body))
        except ValueError as exc:
            return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})


class BulkUpdateMcpPermissionsController(Controller):
    def __init__(self, use_case: BulkUpdateMcpToolPermissionsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            result = await self._use_case.execute(BulkUpdateMcpToolPermissionsInput(**request.body))
        except ValueError as exc:
            return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})
