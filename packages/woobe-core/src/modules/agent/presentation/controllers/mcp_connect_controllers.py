from uuid import UUID

from modules.agent.application.dtos.mcp_oauth_dtos import (
    McpOAuthCompleteInput,
    McpOAuthDevicePollInput,
    McpOAuthDeviceStartInput,
    McpOAuthDisconnectInput,
    McpOAuthStartInput,
    McpOAuthStatusInput,
)
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


def _body_with_uuid_tool_id(request: Request) -> dict:
    body = dict(request.body or {})
    if "tool_id" in body:
        body["tool_id"] = UUID(str(body["tool_id"]))
    return body


class StartMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None: self._use_case = use_case
    async def handle(self, request: Request) -> Response:
        try: result = await self._use_case.execute(McpOAuthStartInput(**request.body))
        except ValueError as exc: return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})

class CompleteMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None: self._use_case = use_case
    async def handle(self, request: Request) -> Response:
        try: result = await self._use_case.execute(McpOAuthCompleteInput(**request.body))
        except ValueError as exc: return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})

class StartMcpDeviceConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None: self._use_case = use_case
    async def handle(self, request: Request) -> Response:
        try: result = await self._use_case.execute(McpOAuthDeviceStartInput(**_body_with_uuid_tool_id(request)))
        except ValueError as exc: return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})

class PollMcpDeviceConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None: self._use_case = use_case
    async def handle(self, request: Request) -> Response:
        try: result = await self._use_case.execute(McpOAuthDevicePollInput(**_body_with_uuid_tool_id(request)))
        except ValueError as exc: return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})

class StatusMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None: self._use_case = use_case
    async def handle(self, request: Request) -> Response:
        try: result = await self._use_case.execute(McpOAuthStatusInput(**request.body))
        except ValueError as exc: return Response(status_code=404, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})

class DisconnectMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None: self._use_case = use_case
    async def handle(self, request: Request) -> Response:
        try: result = await self._use_case.execute(McpOAuthDisconnectInput(**request.body))
        except ValueError as exc: return Response(status_code=404, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})
