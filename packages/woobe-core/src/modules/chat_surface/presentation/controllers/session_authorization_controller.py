from uuid import UUID

from modules.chat_surface.application.dtos.session_authorization import (
    AuthorizeChatSurfaceSessionInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class AuthorizeChatSurfaceSessionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = request.body or {}
        authorized = await self._use_case.execute(
            AuthorizeChatSurfaceSessionInput(
                token=str(body["token"]),
                expected_session_id=UUID(str(body["expected_session_id"])),
                host_origin=str(body["host_origin"]),
                permission=str(body["permission"]),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": authorized.model_dump(mode="json"),
            },
        )


__all__ = ["AuthorizeChatSurfaceSessionController"]
