from modules.agent.application import mcp_oauth, mcp_oauth_flows
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class StartMcpConnectController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_cls = getattr(mcp_oauth, "McpOAuthStartInput")
            result = await self._use_case.execute(input_cls(**request.body))
        except ValueError as exc:
            return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})


class CompleteMcpConnectController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_cls = getattr(mcp_oauth, "McpOAuthCompleteInput")
            result = await self._use_case.execute(input_cls(**request.body))
        except ValueError as exc:
            return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})


class StartMcpDeviceConnectController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_cls = getattr(mcp_oauth_flows, "McpOAuthDeviceStartInput")
            result = await self._use_case.execute(input_cls(**request.body))
        except ValueError as exc:
            return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})


class PollMcpDeviceConnectController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_cls = getattr(mcp_oauth_flows, "McpOAuthDevicePollInput")
            result = await self._use_case.execute(input_cls(**request.body))
        except ValueError as exc:
            return Response(status_code=400, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})


class StatusMcpConnectController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_cls = getattr(mcp_oauth, "McpOAuthStatusInput")
            result = await self._use_case.execute(input_cls(**request.body))
        except ValueError as exc:
            return Response(status_code=404, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})


class DisconnectMcpConnectController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_cls = getattr(mcp_oauth, "McpOAuthDisconnectInput")
            result = await self._use_case.execute(input_cls(**request.body))
        except ValueError as exc:
            return Response(status_code=404, body={"success": False, "message": str(exc), "data": None})
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result.model_dump()})
