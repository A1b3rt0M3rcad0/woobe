from uuid import UUID

from modules.identity.application.interfaces.use_case import UseCase
from shared.contracts.errors import AuthenticationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


def _principal(request: Request) -> AuthenticatedPrincipal:
    if not isinstance(request.principal, AuthenticatedPrincipal):
        raise AuthenticationError("Authentication required")
    return request.principal


class ListWorkspaceMembersAccessController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        data = await self._use_case.execute(
            actor_user_id=principal.user_id,
            workspace_id=UUID(str(request.path_params["workspace_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": data},
        )


class RemoveWorkspaceMemberController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        data = await self._use_case.execute(
            actor_user_id=principal.user_id,
            workspace_id=UUID(str(request.path_params["workspace_id"])),
            target_user_id=UUID(str(request.path_params["target_user_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "removed", "data": data},
        )


class ListWorkspaceInvitesAccessController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        data = await self._use_case.execute(
            actor_user_id=principal.user_id,
            workspace_id=UUID(str(request.path_params["workspace_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": data},
        )


class CancelWorkspaceInviteController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        data = await self._use_case.execute(
            actor_user_id=principal.user_id,
            workspace_id=UUID(str(request.path_params["workspace_id"])),
            invite_id=UUID(str(request.path_params["invite_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "cancelled", "data": data},
        )
