from uuid import UUID

from modules.chat_surface.application.dtos.message_request import MarkMessageRequestInput
from modules.chat_surface.application.use_cases.message_lifecycle import (
    MarkChatSurfaceMessageUseCase,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class MarkChatSurfaceMessageController(Controller):
    def __init__(self, use_case: MarkChatSurfaceMessageUseCase) -> None:
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
