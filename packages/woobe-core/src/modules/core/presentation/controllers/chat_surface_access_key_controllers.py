from uuid import UUID

from modules.core.application.dtos.chat_surface_access_key import (
    ChatSurfaceAccessKeyMutationResult,
    ChatSurfaceAccessKeyState,
    CreateChatSurfaceAccessKeyInput,
    ListChatSurfaceAccessKeysInput,
    RevokeChatSurfaceAccessKeyInput,
    RotateChatSurfaceAccessKeyInput,
)
from modules.core.application.interfaces.use_case import UseCase
from shared.contracts.errors import AuthenticationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


def _principal(request: Request) -> AuthenticatedPrincipal:
    principal = request.principal
    if not isinstance(principal, AuthenticatedPrincipal):
        raise AuthenticationError("User authentication required")
    return principal


def _key_payload(
    key: ChatSurfaceAccessKeyState,
    *,
    secret: str | None = None,
    display_prefix: str | None = None,
) -> dict:
    payload = {
        "id": str(key.id),
        "credential_id": str(key.credential_id),
        "chat_surface_id": str(key.chat_surface_id),
        "name": key.name,
        "description": key.description,
        "prefix": display_prefix or key.key_prefix,
        "scopes": list(key.scopes),
        "status": key.status,
        "last_used_at": key.last_used_at,
        "expires_at": key.expires_at,
        "created_at": key.created_at,
    }
    if secret is not None:
        payload["access_key"] = secret
    return payload


def _mutation_payload(result: ChatSurfaceAccessKeyMutationResult) -> dict:
    return _key_payload(
        result.key,
        secret=result.secret,
        display_prefix=result.display_prefix,
    )


class CreateChatSurfaceAccessKeyController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            CreateChatSurfaceAccessKeyInput(
                project_id=UUID(str(body["project_id"])),
                chat_surface_id=UUID(str(request.path_params["surface_id"])),
                actor_id=principal.user_id,
                name=str(body.get("name") or "Default ChatSurface key"),
                description=body.get("description"),
            )
        )
        return Response(
            status_code=201,
            body={"success": True, "data": _mutation_payload(result)},
        )


class ListChatSurfaceAccessKeysController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _principal(request)
        result = await self._use_case.execute(
            ListChatSurfaceAccessKeysInput(
                chat_surface_id=UUID(str(request.path_params["surface_id"])),
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [_key_payload(item) for item in result],
            },
        )


class RevokeChatSurfaceAccessKeyController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        _principal(request)
        result = await self._use_case.execute(
            RevokeChatSurfaceAccessKeyInput(
                chat_surface_id=UUID(str(request.path_params["surface_id"])),
                api_key_id=UUID(str(request.path_params["api_key_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": _mutation_payload(result)},
        )


class RotateChatSurfaceAccessKeyController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        result = await self._use_case.execute(
            RotateChatSurfaceAccessKeyInput(
                chat_surface_id=UUID(str(request.path_params["surface_id"])),
                api_key_id=UUID(str(request.path_params["api_key_id"])),
                actor_id=principal.user_id,
            )
        )
        return Response(
            status_code=201,
            body={"success": True, "data": _mutation_payload(result)},
        )
