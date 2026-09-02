from datetime import timedelta
from uuid import UUID

from modules.identity.application.auth_types import (
    AuthenticatedUser,
    AuthenticatedWorkspace,
    AuthenticationAttempt,
    IssuedAuthentication,
    IssuedSession,
)
from modules.identity.application.interfaces.authentication import (
    AccessTokenIssuer,
    AuthenticationRepository,
    AuthenticationSessionRepository,
)
from modules.identity.application.interfaces.instance import InstanceRepository
from modules.identity.application.interfaces.outbox import OutboxEventWriter
from modules.identity.application.interfaces.repositories import (
    UserRepository,
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from modules.identity.application.interfaces.workspace_access import WorkspaceAccessRepository
from modules.identity.domain.entities import User, Workspace, WorkspaceMember
from modules.identity.domain.enums import MemberRole, UserStatus
from modules.identity.domain.errors import EmailAlreadyExistsError, InvalidCredentialsError
from shared.contracts.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.contracts.time import utc_now
from shared.security.crypto import hash_password, verify_password


DEFAULT_WORKSPACE_NAME = "My Workspace"


def build_issued_authentication(
    user: User,
    session: IssuedSession,
    token_issuer: AccessTokenIssuer,
    *,
    workspace: Workspace | None = None,
) -> IssuedAuthentication:
    return IssuedAuthentication(
        access_token=token_issuer.issue(user_id=user.id, session_id=session.id),
        refresh_token=session.secret,
        session_id=session.id,
        token_type="Bearer",
        expires_in=token_issuer.ttl_seconds,
        user=AuthenticatedUser(id=user.id, email=user.email, status=user.status.value),
        workspace=(
            AuthenticatedWorkspace(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                status=workspace.status.value,
            )
            if workspace is not None
            else None
        ),
    )


async def _create_owned_workspace(
    *,
    user_id: UUID,
    name: str,
    slug: str,
    workspace_repo: WorkspaceRepository,
    member_repo: WorkspaceMemberRepository,
    outbox: OutboxEventWriter,
) -> Workspace:
    if await workspace_repo.get_by_slug(slug):
        raise ConflictError(f"Workspace with slug '{slug}' already exists")
    workspace = await workspace_repo.save(Workspace(name=name, slug=slug))
    await outbox.write(
        aggregate_type="workspace",
        aggregate_id=workspace.id,
        event_type="workspace.created.v1",
        payload={"name": workspace.name, "slug": workspace.slug},
        routing_key="workspace.created.v1",
        idempotency_key=f"identity:workspace.created.v1:{workspace.id}",
    )
    member = await member_repo.save(
        WorkspaceMember(
            user_id=user_id,
            workspace_id=workspace.id,
            role=MemberRole.owner,
            joined_at=utc_now(),
        )
    )
    await outbox.write(
        aggregate_type="workspace_member",
        aggregate_id=member.id,
        event_type="workspace.member_added.v1",
        payload={
            "user_id": str(user_id),
            "workspace_id": str(workspace.id),
            "role": member.role.value,
        },
        routing_key="workspace.member_added.v1",
        idempotency_key=f"identity:workspace.member_added.v1:{member.id}",
    )
    return workspace


async def _ensure_registration_allowed(
    email: str,
    instance_repo: InstanceRepository,
) -> None:
    state = await instance_repo.get_state()
    if not state.initialized:
        raise ConflictError(
            "Woobe Core is not initialized. Bootstrap the instance before registration."
        )
    if state.signup_mode == "open":
        return
    if state.signup_mode == "disabled":
        raise AuthorizationError("Registration is disabled for this Woobe instance")
    if not await instance_repo.has_active_invite(email):
        raise AuthorizationError(
            "Public registration is disabled. An active Workspace invite is required."
        )


class LoginAuthenticationUseCase:
    def __init__(self, user_repo: UserRepository, session_repo: AuthenticationSessionRepository, token_issuer: AccessTokenIssuer) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._token_issuer = token_issuer

    async def execute(self, *, email: str, password: str, user_agent: str | None, ip_address: str | None) -> IssuedAuthentication:
        user = await self._user_repo.get_by_email(email.strip().lower())
        if user is None or user.status != UserStatus.active or not verify_password(password, user.password):
            raise InvalidCredentialsError("Invalid credentials")
        session = await self._session_repo.issue(user_id=user.id, user_agent=user_agent, ip_address=ip_address)
        return build_issued_authentication(user, session, self._token_issuer)


class RegisterAuthenticationUseCase:
    def __init__(self, instance_repo: InstanceRepository, user_repo: UserRepository, workspace_repo: WorkspaceRepository, member_repo: WorkspaceMemberRepository, outbox: OutboxEventWriter, session_repo: AuthenticationSessionRepository, token_issuer: AccessTokenIssuer) -> None:
        self._instance_repo = instance_repo
        self._user_repo = user_repo
        self._workspace_repo = workspace_repo
        self._member_repo = member_repo
        self._outbox = outbox
        self._session_repo = session_repo
        self._token_issuer = token_issuer

    async def execute(self, *, email: str, password: str, user_agent: str | None, ip_address: str | None) -> IssuedAuthentication:
        normalized_email = email.strip().lower()
        await _ensure_registration_allowed(normalized_email, self._instance_repo)
        if await self._user_repo.get_by_email(normalized_email):
            raise EmailAlreadyExistsError(normalized_email)
        user = await self._user_repo.save(User(email=normalized_email, password=hash_password(password)))
        await self._outbox.write(aggregate_type="user", aggregate_id=user.id, event_type="user.created.v1", payload={"email": user.email}, routing_key="user.created.v1", idempotency_key=f"identity:user.created.v1:{user.id}")
        workspace = await _create_owned_workspace(user_id=user.id, name=DEFAULT_WORKSPACE_NAME, slug=f"workspace-{str(user.id)[:8]}", workspace_repo=self._workspace_repo, member_repo=self._member_repo, outbox=self._outbox)
        session = await self._session_repo.issue(user_id=user.id, user_agent=user_agent, ip_address=ip_address)
        return build_issued_authentication(user, session, self._token_issuer, workspace=workspace)


class CreateOwnedWorkspaceUseCase:
    def __init__(self, user_repo: UserRepository, workspace_repo: WorkspaceRepository, member_repo: WorkspaceMemberRepository, outbox: OutboxEventWriter) -> None:
        self._user_repo = user_repo
        self._workspace_repo = workspace_repo
        self._member_repo = member_repo
        self._outbox = outbox

    async def execute(self, *, user_id: UUID, name: str, slug: str) -> Workspace:
        user = await self._user_repo.get_by_id(user_id)
        if user is None or user.status != UserStatus.active:
            raise AuthenticationError("Authentication required")
        return await _create_owned_workspace(user_id=user.id, name=name.strip(), slug=slug.strip().lower(), workspace_repo=self._workspace_repo, member_repo=self._member_repo, outbox=self._outbox)


class RefreshAuthenticationUseCase:
    def __init__(self, user_repo: UserRepository, session_repo: AuthenticationSessionRepository, token_issuer: AccessTokenIssuer) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._token_issuer = token_issuer

    async def execute(self, *, session_id: UUID, secret: str, user_agent: str | None, ip_address: str | None) -> AuthenticationAttempt:
        rotation = await self._session_repo.rotate(session_id=session_id, secret=secret, user_agent=user_agent, ip_address=ip_address)
        if rotation.session is None:
            return AuthenticationAttempt(error=rotation.error or "Invalid refresh session")
        user = await self._user_repo.get_by_id(rotation.session.user_id)
        if user is None or user.status != UserStatus.active:
            await self._session_repo.revoke_all(rotation.session.user_id)
            return AuthenticationAttempt(error="Invalid refresh session")
        return AuthenticationAttempt(authentication=build_issued_authentication(user, rotation.session, self._token_issuer))


class LogoutAuthenticationUseCase:
    def __init__(self, session_repo: AuthenticationSessionRepository) -> None:
        self._session_repo = session_repo

    async def execute(self, *, session_id: UUID | None, secret: str | None) -> None:
        await self._session_repo.revoke(session_id=session_id, secret=secret)


class GetAuthenticatedUserUseCase:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, user_id: UUID) -> AuthenticatedUser:
        user = await self._user_repo.get_by_id(user_id)
        if user is None or user.status != UserStatus.active:
            raise AuthenticationError("Authentication required")
        return AuthenticatedUser(id=user.id, email=user.email, status=user.status.value)


class ListAuthenticatedWorkspacesUseCase:
    def __init__(self, auth_repo: AuthenticationRepository) -> None:
        self._auth_repo = auth_repo

    async def execute(self, user_id: UUID) -> list[dict[str, object]]:
        return await self._auth_repo.list_workspaces(user_id)


class ListPendingWorkspaceInvitesUseCase:
    def __init__(self, user_repo: UserRepository, auth_repo: AuthenticationRepository) -> None:
        self._user_repo = user_repo
        self._auth_repo = auth_repo

    async def execute(self, user_id: UUID) -> list[dict[str, object]]:
        user = await self._user_repo.get_by_id(user_id)
        if user is None or user.status != UserStatus.active:
            raise AuthenticationError("Authentication required")
        return await self._auth_repo.list_pending_invites(user.email)


class CreateWorkspaceInviteUseCase:
    def __init__(self, workspace_repo: WorkspaceRepository, auth_repo: AuthenticationRepository, access_repo: WorkspaceAccessRepository, outbox: OutboxEventWriter) -> None:
        self._workspace_repo = workspace_repo
        self._auth_repo = auth_repo
        self._access_repo = access_repo
        self._outbox = outbox

    async def execute(self, *, actor_user_id: UUID, workspace_id: UUID, email: str, role: MemberRole, project_ids: list[UUID]) -> object:
        normalized_email = email.strip().lower()
        if not normalized_email:
            raise ConflictError("Invite email is required")
        await self._access_repo.require_role_assignment(actor_user_id=actor_user_id, workspace_id=workspace_id, target_role=role.value)
        if await self._workspace_repo.get_by_id(workspace_id) is None:
            raise NotFoundError("Workspace not found")
        now = utc_now()
        invite = await self._auth_repo.create_invite(actor_user_id=actor_user_id, workspace_id=workspace_id, email=normalized_email, role=role, project_ids=project_ids, expires_at=now + timedelta(days=7), now=now)
        await self._outbox.write(aggregate_type="workspace_invite", aggregate_id=invite.id, event_type="workspace.invite_created.v1", payload={"workspace_id": str(workspace_id), "email": normalized_email, "role": role.value, "project_ids": [str(project_id) for project_id in dict.fromkeys(project_ids)]}, routing_key="workspace.invite_created.v1", idempotency_key=f"identity:workspace.invite_created.v1:{invite.id}:{int(now.timestamp())}")
        return invite


class AcceptWorkspaceInviteUseCase:
    def __init__(self, user_repo: UserRepository, auth_repo: AuthenticationRepository, access_repo: WorkspaceAccessRepository, outbox: OutboxEventWriter) -> None:
        self._user_repo = user_repo
        self._auth_repo = auth_repo
        self._access_repo = access_repo
        self._outbox = outbox

    async def execute(self, *, user_id: UUID, invite_id: UUID) -> Workspace:
        user = await self._user_repo.get_by_id(user_id)
        if user is None or user.status != UserStatus.active:
            raise AuthenticationError("Authentication required")
        await self._access_repo.require_valid_invite_acceptance(user_id=user_id, invite_id=invite_id)
        accepted = await self._auth_repo.accept_invite(user=user, invite_id=invite_id, now=utc_now())
        if accepted.membership_changed:
            await self._outbox.write(aggregate_type="workspace_member", aggregate_id=accepted.member_id, event_type="workspace.member_added.v1", payload={"user_id": str(user.id), "workspace_id": str(accepted.workspace.id), "role": accepted.role.value}, routing_key="workspace.member_added.v1", idempotency_key=f"identity:workspace.member_added.v1:{accepted.member_id}")
        return accepted.workspace
