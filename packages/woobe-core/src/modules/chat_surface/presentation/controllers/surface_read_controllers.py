from uuid import UUID

from modules.chat_surface.application.dtos.surface_read import (
    GetChatSurfaceInput,
    ListChatSurfacesInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from modules.chat_surface.presentation.mappers import chat_surface_payload
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListChatSurfacesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            ListChatSurfacesInput(
                project_id=UUID(str(request.path_params["project_id"])),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [chat_surface_payload(item) for item in result],
            },
        )


class GetChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            GetChatSurfaceInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": chat_surface_payload(result)},
        )
