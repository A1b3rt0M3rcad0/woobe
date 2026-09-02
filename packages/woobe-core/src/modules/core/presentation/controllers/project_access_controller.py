from uuid import UUID

from modules.core.application.interfaces.use_case import UseCase
from shared.contracts.errors import AuthenticationError, ValidationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


def _principal_user_id(request: Request) -> UUID:
    principal = request.principal
    if not isinstance(principal, AuthenticatedPrincipal):
        raise AuthenticationError("Authentication required")
    return principal.user_id


class ListAccessibleProjectsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        workspace_id = request.query_params.get("workspace_id")
        if not workspace_id:
            return Response(
                status_code=200,
                body={"success": True, "message": "ok", "data": []},
            )
        try:
            workspace_uuid = UUID(str(workspace_id))
        except ValueError as exc:
            raise ValidationError("Invalid workspace_id") from exc
        data = await self._use_case.execute(
            user_id=_principal_user_id(request),
            workspace_id=workspace_uuid,
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": data},
        )


class ListProjectsForAccessManagementController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        data = await self._use_case.execute(
            user_id=_principal_user_id(request),
            workspace_id=UUID(str(request.path_params["workspace_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": data},
        )


class ListProjectMembersController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        data = await self._use_case.execute(
            user_id=_principal_user_id(request),
            project_id=UUID(str(request.path_params["access_project_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": data},
        )


class GrantProjectSubjectAccessController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body or {})
        subject_type = body.get("subject_type")
        subject_id = body.get("subject_id")
        if subject_type not in {"member", "invite"}:
            raise ValidationError("subject_type must be member or invite")
        try:
            subject_uuid = UUID(str(subject_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Invalid subject_id") from exc
        data = await self._use_case.execute(
            actor_user_id=_principal_user_id(request),
            project_id=UUID(str(request.path_params["access_project_id"])),
            subject_type=subject_type,
            subject_id=subject_uuid,
        )
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": data},
        )


class RevokeProjectSubjectAccessController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        subject_type = str(request.path_params["subject_type"])
        if subject_type not in {"member", "invite"}:
            raise ValidationError("subject_type must be member or invite")
        await self._use_case.execute(
            actor_user_id=_principal_user_id(request),
            project_id=UUID(str(request.path_params["access_project_id"])),
            subject_type=subject_type,
            subject_id=UUID(str(request.path_params["subject_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "deleted", "data": None},
        )


class GrantProjectAccessController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body or {})
        email = body.get("email")
        if not isinstance(email, str) or not email.strip():
            raise ValidationError("email is required")
        data = await self._use_case.execute(
            actor_user_id=_principal_user_id(request),
            project_id=UUID(str(request.path_params["access_project_id"])),
            email=email,
        )
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": data},
        )


class RevokeProjectAccessController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        await self._use_case.execute(
            actor_user_id=_principal_user_id(request),
            project_id=UUID(str(request.path_params["access_project_id"])),
            target_user_id=UUID(str(request.path_params["target_user_id"])),
        )
        return Response(
            status_code=200,
            body={"success": True, "message": "deleted", "data": None},
        )
