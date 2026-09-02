from uuid import UUID

from modules.identity.application.dtos import CreateWorkspaceInput, LoginInput, RegisterInput
from modules.identity.application.interfaces.use_case import UseCase
from modules.identity.domain.enums import MemberRole
from modules.identity.domain.errors import InvalidCredentialsError
from modules.identity.presentation.authentication_response import (
    AuthenticationCookiePolicy,
    authentication_response,
    csrf_response,
    logout_response,
)
from shared.contracts.errors import AuthenticationError, ValidationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller
from shared.security.principal import AuthenticatedPrincipal


def _principal(request: Request) -> AuthenticatedPrincipal:
    if not isinstance(request.principal, AuthenticatedPrincipal):
        raise AuthenticationError("Authentication required")
    return request.principal


class LoginAuthenticationController(Controller):
    def __init__(self, use_case: UseCase, cookie_policy: AuthenticationCookiePolicy) -> None:
        self._use_case = use_case
        self._cookie_policy = cookie_policy

    async def handle(self, request: Request) -> Response:
        data = LoginInput(**(request.body or {}))
        try:
            result = await self._use_case.execute(email=data.email, password=data.password, user_agent=request.headers.get("user-agent"), ip_address=request.client_ip)
        except InvalidCredentialsError:
            return Response(status_code=401, body={"success": False, "message": "Invalid credentials", "data": None})
        return authentication_response(request, result, self._cookie_policy, status_code=200)


class RegisterAuthenticationController(Controller):
    def __init__(self, use_case: UseCase, cookie_policy: AuthenticationCookiePolicy) -> None:
        self._use_case = use_case
        self._cookie_policy = cookie_policy

    async def handle(self, request: Request) -> Response:
        data = RegisterInput(**(request.body or {}))
        result = await self._use_case.execute(email=data.email, password=data.password, user_agent=request.headers.get("user-agent"), ip_address=request.client_ip)
        return authentication_response(request, result, self._cookie_policy, status_code=201)


class RefreshAuthenticationController(Controller):
    def __init__(self, use_case: UseCase, cookie_policy: AuthenticationCookiePolicy) -> None:
        self._use_case = use_case
        self._cookie_policy = cookie_policy

    async def handle(self, request: Request) -> Response:
        secret = request.cookies.get(self._cookie_policy.refresh_cookie_name)
        session_value = request.cookies.get(f"{self._cookie_policy.refresh_cookie_name}_session")
        if not secret or not session_value:
            return Response(status_code=401, body={"success": False, "message": "Invalid refresh session", "data": None})
        try:
            session_id = UUID(session_value)
        except ValueError:
            return Response(status_code=401, body={"success": False, "message": "Invalid refresh session", "data": None})
        attempt = await self._use_case.execute(session_id=session_id, secret=secret, user_agent=request.headers.get("user-agent"), ip_address=request.client_ip)
        if attempt.authentication is None:
            return Response(status_code=401, body={"success": False, "message": attempt.error or "Invalid refresh session", "data": None})
        return authentication_response(request, attempt.authentication, self._cookie_policy, status_code=200)


class LogoutAuthenticationController(Controller):
    def __init__(self, use_case: UseCase, cookie_policy: AuthenticationCookiePolicy) -> None:
        self._use_case = use_case
        self._cookie_policy = cookie_policy

    async def handle(self, request: Request) -> Response:
        secret = request.cookies.get(self._cookie_policy.refresh_cookie_name)
        session_value = request.cookies.get(f"{self._cookie_policy.refresh_cookie_name}_session")
        session_id: UUID | None = None
        if session_value:
            try:
                session_id = UUID(session_value)
            except ValueError:
                session_id = None
        await self._use_case.execute(session_id=session_id, secret=secret)
        return logout_response(request, self._cookie_policy)


class GetAuthenticatedUserController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        user = await self._use_case.execute(principal.user_id)
        return Response(status_code=200, body={"success": True, "message": "ok", "data": {"id": str(user.id), "email": user.email, "status": user.status}})


class ListAuthenticatedWorkspacesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        data = await self._use_case.execute(_principal(request).user_id)
        return Response(status_code=200, body={"success": True, "message": "ok", "data": data})


class ListPendingWorkspaceInvitesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        data = await self._use_case.execute(_principal(request).user_id)
        return Response(status_code=200, body={"success": True, "message": "ok", "data": data})


class CreateOwnedWorkspaceController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        data = CreateWorkspaceInput(**(request.body or {}))
        workspace = await self._use_case.execute(user_id=principal.user_id, name=data.name, slug=data.slug)
        return Response(status_code=201, body={"success": True, "message": "created", "data": {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug, "status": workspace.status.value if hasattr(workspace.status, "value") else workspace.status, "created_at": workspace.created_at}})


class CreateWorkspaceInviteController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        principal = _principal(request)
        body = dict(request.body or {})
        role_value = body.get("role", "member")
        email = body.get("email")
        project_values = body.get("project_ids", [])
        if not isinstance(role_value, str) or not isinstance(email, str) or not email.strip():
            raise ValidationError("Invalid invite role or email")
        if not isinstance(project_values, list):
            raise ValidationError("project_ids must be a list")
        try:
            role = MemberRole(role_value.strip().lower())
            project_ids = [UUID(str(value)) for value in project_values]
        except (ValueError, TypeError) as exc:
            raise ValidationError("Invalid invite role or Project id") from exc
        if role not in {MemberRole.member, MemberRole.admin}:
            raise ValidationError("Only member and admin invitation roles are supported in the MVP")
        invite = await self._use_case.execute(actor_user_id=principal.user_id, workspace_id=UUID(str(request.path_params["workspace_id"])), email=email, role=role, project_ids=project_ids)
        return Response(status_code=201, body={"success": True, "message": "created", "data": {"id": invite.id, "workspace_id": invite.workspace_id, "email": invite.email, "role": invite.role.value, "status": invite.status.value, "expires_at": invite.expires_at, "created_at": invite.created_at, "project_ids": project_ids, "project_count": len(project_ids)}})


class AcceptWorkspaceInviteController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        workspace = await self._use_case.execute(user_id=_principal(request).user_id, invite_id=UUID(str(request.path_params["invite_id"])))
        return Response(status_code=200, body={"success": True, "message": "accepted", "data": {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug, "status": workspace.status.value if hasattr(workspace.status, "value") else workspace.status, "created_at": workspace.created_at}})


class CsrfController(Controller):
    def __init__(self, cookie_policy: AuthenticationCookiePolicy) -> None:
        self._cookie_policy = cookie_policy

    async def handle(self, request: Request) -> Response:
        _principal(request)
        return csrf_response(request, self._cookie_policy)
