from uuid import UUID

from modules.chat_surface.application.dtos.surface_read import (
    GetChatSurfaceInput,
    GetPublicChatSurfaceInput,
    ListChatSurfacesInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from modules.chat_surface.presentation.mappers import chat_surface_payload
from shared.contracts.errors import AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


def _require_authenticated_user(request: Request) -> None:
    if not isinstance(request.principal, AuthenticatedPrincipal):
        raise AuthorizationError("User authentication required")


class ListChatSurfacesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _require_authenticated_user(request)
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
        _require_authenticated_user(request)
        result = await self._use_case.execute(
            GetChatSurfaceInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": chat_surface_payload(result)},
        )


class GetPublicChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        result = await self._use_case.execute(
            GetPublicChatSurfaceInput(
                public_id=str(request.path_params["public_id"]),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": chat_surface_payload(result)},
        )


__all__ = [
    "GetChatSurfaceController",
    "GetPublicChatSurfaceController",
    "ListChatSurfacesController",
]
