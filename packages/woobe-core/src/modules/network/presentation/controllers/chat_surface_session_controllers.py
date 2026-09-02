from modules.network.application.dtos.chat_surface_session import (
    CloseNetworkChatSurfaceSessionInput,
    CreateNetworkChatSurfaceSessionInput,
)
from modules.network.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class CreateNetworkChatSurfaceSessionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            CreateNetworkChatSurfaceSessionInput.model_validate(request.body or {})
        )
        return Response(
            status_code=201,
            body={"success": True, "data": result.model_dump(mode="json")},
        )


class CloseNetworkChatSurfaceSessionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            CloseNetworkChatSurfaceSessionInput.model_validate(request.body or {})
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result.model_dump(mode="json")},
        )


__all__ = [
    "CloseNetworkChatSurfaceSessionController",
    "CreateNetworkChatSurfaceSessionController",
]
