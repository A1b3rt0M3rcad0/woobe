from uuid import UUID

from modules.chat_surface.application.dtos.session_read import (
    GetChatSurfaceActivityInput,
    ListChatSurfaceSessionsInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListChatSurfaceSessionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            ListChatSurfaceSessionsInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                limit=int(request.query_params.get("limit", 50)),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [item.model_dump(mode="json") for item in result],
            },
        )


class GetChatSurfaceActivityController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            GetChatSurfaceActivityInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": result.model_dump(mode="json"),
            },
        )
