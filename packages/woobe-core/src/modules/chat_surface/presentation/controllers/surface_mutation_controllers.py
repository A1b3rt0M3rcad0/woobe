from uuid import UUID

from modules.chat_surface.application.dtos.surface_mutation import (
    ChangeChatSurfaceStatusInput,
    UpdateChatSurfaceInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from modules.chat_surface.presentation.mappers import chat_surface_payload
from modules.chat_surface.presentation.schemas import UpdateChatSurfaceRequest
from shared.contracts.errors import AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


def _require_authenticated_user(request: Request) -> None:
    if not isinstance(request.principal, AuthenticatedPrincipal):
        raise AuthorizationError("User authentication required")


class UpdateChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _require_authenticated_user(request)
        payload = UpdateChatSurfaceRequest.model_validate(request.body or {})
        changes = payload.model_dump(exclude_unset=True)
        result = await self._use_case.execute(
            UpdateChatSurfaceInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                **changes,
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": chat_surface_payload(result)},
        )


class DisableChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _require_authenticated_user(request)
        result = await self._use_case.execute(
            ChangeChatSurfaceStatusInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": chat_surface_payload(result)},
        )


class ArchiveChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _require_authenticated_user(request)
        result = await self._use_case.execute(
            ChangeChatSurfaceStatusInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": chat_surface_payload(result)},
        )


__all__ = [
    "ArchiveChatSurfaceController",
    "DisableChatSurfaceController",
    "UpdateChatSurfaceController",
]
