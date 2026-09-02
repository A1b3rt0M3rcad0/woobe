from uuid import UUID

from modules.chat_surface.application.dtos.message_request import (
    BeginMessageRequestInput,
    LatestMessageRequestInput,
    MarkMessageRequestInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class BeginChatSurfaceMessageController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = request.body or {}
        result = await self._use_case.execute(
            BeginMessageRequestInput(
                surface_id=UUID(str(body["surface_id"])),
                session_binding_id=UUID(str(body["session_binding_id"])),
                idempotency_key=str(body["idempotency_key"]),
                metadata=body.get("metadata"),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": {
                    "request": result.request.model_dump(mode="json"),
                    "created": result.created,
                },
            },
        )


class LatestChatSurfaceMessageController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            LatestMessageRequestInput(
                session_binding_id=UUID(str(request.path_params["session_binding_id"])),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": result.model_dump(mode="json") if result is not None else None,
            },
        )


class MarkChatSurfaceMessageController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = request.body or {}
        result = await self._use_case.execute(
            MarkMessageRequestInput(
                request_id=UUID(str(request.path_params["request_id"])),
                status=str(body["status"]),
                target_run_id=(
                    UUID(str(body["target_run_id"]))
                    if body.get("target_run_id") is not None
                    else None
                ),
                error_code=body.get("error_code"),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": result.model_dump(mode="json") if result is not None else None,
            },
        )
