from uuid import UUID

from modules.chat_surface.application.dtos.surface_mutation import (
    ActivateChatSurfaceInput,
    ChangeChatSurfaceStatusInput,
    CreateChatSurfaceInput,
    RefreshChatSurfaceReleaseInput,
    UpdateChatSurfaceInput,
)
from modules.chat_surface.application.interfaces.use_case import UseCase
from modules.chat_surface.presentation.mappers import chat_surface_payload
from modules.chat_surface.presentation.schemas import (
    CreateChatSurfaceRequest,
    UpdateChatSurfaceRequest,
)
from shared.contracts.errors import AuthorizationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


def _require_authenticated_user(request: Request) -> AuthenticatedPrincipal:
    if not isinstance(request.principal, AuthenticatedPrincipal):
        raise AuthorizationError("User authentication required")
    return request.principal


class CreateChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _require_authenticated_user(request)
        raw = dict(request.body or {})
        payload = CreateChatSurfaceRequest.model_validate(raw)
        result = await self._use_case.execute(
            CreateChatSurfaceInput(
                project_id=UUID(str(request.path_params["project_id"])),
                actor_id=principal.user_id,
                target_release_id=UUID(str(raw["target_release_id"])),
                **payload.model_dump(),
            )
        )
        return Response(
            status_code=201,
            body={"success": True, "data": chat_surface_payload(result)},
        )


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


class RefreshChatSurfaceReleaseController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _require_authenticated_user(request)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            RefreshChatSurfaceReleaseInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                target_release_id=UUID(str(body["target_release_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": chat_surface_payload(result)},
        )


class ActivateChatSurfaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _require_authenticated_user(request)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            ActivateChatSurfaceInput(
                surface_id=UUID(str(request.path_params["surface_id"])),
                expected_target_release_id=UUID(
                    str(body["expected_target_release_id"])
                ),
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
    "ActivateChatSurfaceController",
    "ArchiveChatSurfaceController",
    "CreateChatSurfaceController",
    "DisableChatSurfaceController",
    "RefreshChatSurfaceReleaseController",
    "UpdateChatSurfaceController",
]
