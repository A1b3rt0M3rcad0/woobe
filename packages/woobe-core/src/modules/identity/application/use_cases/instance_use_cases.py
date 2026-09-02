from uuid import UUID

from modules.identity.application.interfaces.authentication import (
    AccessTokenIssuer,
    AuthenticationSessionRepository,
)
from modules.identity.application.interfaces.instance import InstanceRepository
from modules.identity.application.interfaces.outbox import OutboxEventWriter
from modules.identity.application.interfaces.repositories import (
    UserRepository,
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from modules.identity.application.use_cases.authentication_use_cases import (
    DEFAULT_WORKSPACE_NAME,
    build_issued_authentication,
)
from modules.identity.domain.entities import User, Workspace, WorkspaceMember
from modules.identity.domain.enums import MemberRole
from modules.identity.domain.errors import EmailAlreadyExistsError
from shared.contracts.errors import ConflictError, NotFoundError
from shared.contracts.time import utc_now
from shared.security.crypto import hash_password


class InstanceStatusUseCase:
    def __init__(self, instance_repo: InstanceRepository, *, edition: str) -> None:
        self._instance_repo = instance_repo
        self._edition = edition

    async def execute(self) -> dict[str, object]:
        state = await self._instance_repo.get_state()
        return {
            "initialized": state.initialized,
            "edition": self._edition,
            "signup_mode": state.signup_mode,
            "telemetry_enabled": state.telemetry_enabled,
            "requires_existing_owner_bootstrap": not state.initialized and state.user_count > 0,
        }


class BootstrapInstanceUseCase:
    def __init__(
        self,
        instance_repo: InstanceRepository,
        user_repo: UserRepository,
        workspace_repo: WorkspaceRepository,
        member_repo: WorkspaceMemberRepository,
        outbox: OutboxEventWriter,
        session_repo: AuthenticationSessionRepository,
        token_issuer: AccessTokenIssuer,
        *,
        edition: str,
    ) -> None:
        self._instance_repo = instance_repo
        self._user_repo = user_repo
        self._workspace_repo = workspace_repo
        self._member_repo = member_repo
        self._outbox = outbox
        self._session_repo = session_repo
        self._token_issuer = token_issuer
        self._edition = edition

    async def execute(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ):
        if self._edition != "core":
            raise ConflictError("Instance bootstrap is only available in Woobe Core")
        normalized_email = email.strip().lower()
        now = utc_now()
        if not await self._instance_repo.claim_bootstrap(now):
            raise ConflictError("Woobe instance is already initialized or being initialized")
        state = await self._instance_repo.get_state()
        if state.user_count > 0:
            raise ConflictError(
                "Existing Woobe installation detected. Run the explicit existing-owner bootstrap command."
            )
        if await self._user_repo.get_by_email(normalized_email):
            raise EmailAlreadyExistsError(normalized_email)

        user = await self._user_repo.save(
            User(email=normalized_email, password=hash_password(password))
        )
        await self._outbox.write(
            aggregate_type="user",
            aggregate_id=user.id,
            event_type="user.created.v1",
            payload={"email": user.email},
            routing_key="user.created.v1",
            idempotency_key=f"identity:user.created.v1:{user.id}",
        )
        workspace = await self._workspace_repo.save(
            Workspace(
                name=DEFAULT_WORKSPACE_NAME,
                slug=f"workspace-{str(user.id)[:8]}",
            )
        )
        await self._outbox.write(
            aggregate_type="workspace",
            aggregate_id=workspace.id,
            event_type="workspace.created.v1",
            payload={"name": workspace.name, "slug": workspace.slug},
            routing_key="workspace.created.v1",
            idempotency_key=f"identity:workspace.created.v1:{workspace.id}",
        )
        member = await self._member_repo.save(
            WorkspaceMember(
                user_id=user.id,
                workspace_id=workspace.id,
                role=MemberRole.owner,
                joined_at=now,
            )
        )
        await self._outbox.write(
            aggregate_type="workspace_member",
            aggregate_id=member.id,
            event_type="workspace.member_added.v1",
            payload={
                "user_id": str(user.id),
                "workspace_id": str(workspace.id),
                "role": member.role.value,
            },
            routing_key="workspace.member_added.v1",
            idempotency_key=f"identity:workspace.member_added.v1:{member.id}",
        )
        session = await self._session_repo.issue(
            user_id=user.id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self._instance_repo.set_owner(user.id, now)
        return build_issued_authentication(
            user,
            session,
            self._token_issuer,
            workspace=workspace,
        )


class BootstrapExistingOwnerUseCase:
    def __init__(self, instance_repo: InstanceRepository, *, edition: str) -> None:
        self._instance_repo = instance_repo
        self._edition = edition

    async def execute(self, *, owner_email: str) -> UUID:
        if self._edition != "core":
            raise ConflictError(
                "Existing-owner bootstrap is only available in Woobe Core"
            )
        owner_id = await self._instance_repo.find_existing_owner(owner_email)
        if owner_id is None:
            raise NotFoundError(
                "No active Workspace owner exists with the supplied email"
            )
        if not await self._instance_repo.initialize_existing_owner(owner_id, utc_now()):
            raise ConflictError("Woobe instance is already initialized")
        return owner_id
