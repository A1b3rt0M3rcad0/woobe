from modules.agent.application.dtos.chat_surface_session import (
    CloseAgentChatSurfaceSessionInput,
    CreateAgentChatSurfaceSessionInput,
)
from modules.agent.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class CreateAgentChatSurfaceSessionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            CreateAgentChatSurfaceSessionInput.model_validate(request.body or {})
        )
        return Response(
            status_code=201,
            body={"success": True, "data": result.model_dump(mode="json")},
        )


class CloseAgentChatSurfaceSessionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            CloseAgentChatSurfaceSessionInput.model_validate(request.body or {})
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result.model_dump(mode="json")},
        )


__all__ = [
    "CloseAgentChatSurfaceSessionController",
    "CreateAgentChatSurfaceSessionController",
]
