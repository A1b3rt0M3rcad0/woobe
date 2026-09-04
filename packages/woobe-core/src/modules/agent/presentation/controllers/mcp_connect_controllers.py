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
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


def _body_with_uuid_tool_id(request: OperationRequest) -> dict:
    body = dict(request.body or {})
    if "tool_id" in body:
        body["tool_id"] = UUID(str(body["tool_id"]))
    return body


class StartMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            result = await self._use_case.execute(McpOAuthStartInput(**request.body))
        except ValueError as exc:
            return _error(OperationOutcome.INVALID, exc)
        return _success(result)


class CompleteMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            result = await self._use_case.execute(
                McpOAuthCompleteInput(**request.body)
            )
        except ValueError as exc:
            return _error(OperationOutcome.INVALID, exc)
        return _success(result)


class StartMcpDeviceConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            result = await self._use_case.execute(
                McpOAuthDeviceStartInput(**_body_with_uuid_tool_id(request))
            )
        except ValueError as exc:
            return _error(OperationOutcome.INVALID, exc)
        return _success(result)


class PollMcpDeviceConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            result = await self._use_case.execute(
                McpOAuthDevicePollInput(**_body_with_uuid_tool_id(request))
            )
        except ValueError as exc:
            return _error(OperationOutcome.INVALID, exc)
        return _success(result)


class StatusMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            result = await self._use_case.execute(McpOAuthStatusInput(**request.body))
        except ValueError as exc:
            return _error(OperationOutcome.NOT_FOUND, exc)
        return _success(result)


class DisconnectMcpConnectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            result = await self._use_case.execute(
                McpOAuthDisconnectInput(**request.body)
            )
        except ValueError as exc:
            return _error(OperationOutcome.NOT_FOUND, exc)
        return _success(result)


def _error(outcome: OperationOutcome, exc: ValueError) -> OperationResult:
    return OperationResult(
        outcome=outcome,
        body={"success": False, "message": str(exc), "data": None},
    )


def _success(result) -> OperationResult:
    return OperationResult(
        outcome=OperationOutcome.SUCCESS,
        body={"success": True, "message": "ok", "data": result.model_dump()},
    )
