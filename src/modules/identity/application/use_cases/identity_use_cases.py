import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID

from modules.identity.domain.entities import (
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
    User,
)
from modules.identity.domain.enums import InviteStatus, MemberRole
from modules.identity.domain.errors import (
    EmailAlreadyExistsError,
    WorkspaceNotFoundError,
    UserNotFoundError,
)
from modules.identity.domain.repositories import (
    WorkspaceInviteRepository,
    WorkspaceMemberRepository,
    WorkspaceRepository,
    UserRepository,
)
from modules.identity.application.dtos import (
    AddMemberInput,
    AddMemberOutput,
    CreateWorkspaceInput,
    CreateWorkspaceOutput,
    GetCurrentUserInput,
    GetCurrentUserOutput,
    GetWorkspaceInput,
    GetWorkspaceOutput,
    GetUserInput,
    GetUserOutput,
    InviteUserInput,
    InviteUserOutput,
    ListInvitesInput,
    ListInvitesOutput,
    ListMembersInput,
    ListMembersOutput,
    ListWorkspacesInput,
    ListWorkspacesOutput,
    LoginInput,
    LoginOutput,
    RegisterInput,
    RegisterOutput,
    UpdateWorkspaceInput,
    UpdateWorkspaceOutput,
    CreateUserInput,
    CreateUserOutput,
)
from shared.infra.errors import ConflictError
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.infra.crypto import hash_password, verify_password


class CreateUserUseCase:

    def __init__(
        self,
        user_repo: UserRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._user_repo = user_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateUserInput) -> CreateUserOutput:
        existing = await self._user_repo.get_by_email(input_dto.email)
        if existing:
            raise EmailAlreadyExistsError(input_dto.email)

        password_hash = hash_password(input_dto.password)
        user = User(email=input_dto.email, password=password_hash)
        saved = await self._user_repo.save(user)

        await self._outbox.write(
            aggregate_type="user",
            aggregate_id=saved.id,
            event_type="user.created.v1",
            payload={"email": saved.email},
            routing_key="user.created.v1",
            idempotency_key=f"identity:user.created.v1:{saved.id}",
        )

        return CreateUserOutput(
            id=saved.id,
            email=saved.email,
            status=saved.status,
            created_at=saved.created_at,
        )


class CreateWorkspaceUseCase:

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._outbox = outbox

    async def execute(
        self, input_dto: CreateWorkspaceInput
    ) -> CreateWorkspaceOutput:
        existing = await self._workspace_repo.get_by_slug(input_dto.slug)
        if existing:
            raise ConflictError(f"Workspace with slug '{input_dto.slug}' already exists")

        workspace = Workspace(name=input_dto.name, slug=input_dto.slug)
        saved = await self._workspace_repo.save(workspace)

        await self._outbox.write(
            aggregate_type="workspace",
            aggregate_id=saved.id,
            event_type="workspace.created.v1",
            payload={"name": saved.name, "slug": saved.slug},
            routing_key="workspace.created.v1",
            idempotency_key=f"identity:workspace.created.v1:{saved.id}",
        )

        return CreateWorkspaceOutput(
            id=saved.id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
        )


class AddMemberToWorkspaceUseCase:

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        user_repo: UserRepository,
        member_repo: WorkspaceMemberRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._user_repo = user_repo
        self._member_repo = member_repo
        self._outbox = outbox

    async def execute(self, input_dto: AddMemberInput) -> AddMemberOutput:
        workspace = await self._workspace_repo.get_by_id(input_dto.workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError(input_dto.workspace_id)

        user = await self._user_repo.get_by_id(input_dto.user_id)
        if not user:
            raise UserNotFoundError(input_dto.user_id)

        existing_member = await self._member_repo.get_by_workspace_and_user(
            input_dto.workspace_id, input_dto.user_id
        )
        if existing_member:
            raise ConflictError("User is already a member of this workspace")

        member = WorkspaceMember(
            user_id=input_dto.user_id,
            workspace_id=input_dto.workspace_id,
            role=input_dto.role,
            joined_at=datetime.now(UTC),
        )
        saved = await self._member_repo.save(member)

        await self._outbox.write(
            aggregate_type="workspace_member",
            aggregate_id=saved.id,
            event_type="workspace.member_added.v1",
            payload={
                "user_id": str(saved.user_id),
                "workspace_id": str(saved.workspace_id),
                "role": saved.role.value,
            },
            routing_key="workspace.member_added.v1",
            idempotency_key=f"identity:workspace.member_added.v1:{saved.id}",
        )

        return AddMemberOutput(
            id=saved.id,
            user_id=saved.user_id,
            workspace_id=saved.workspace_id,
            role=saved.role,
            status=saved.status,
            joined_at=saved.joined_at,
        )


class UpdateWorkspaceUseCase:

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._outbox = outbox

    async def execute(
        self, workspace_id: UUID, input_dto: UpdateWorkspaceInput
    ) -> UpdateWorkspaceOutput:
        workspace = await self._workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError(workspace_id)

        if input_dto.name is not None:
            workspace.name = input_dto.name
        if input_dto.slug is not None:
            existing = await self._workspace_repo.get_by_slug(input_dto.slug)
            if existing and existing.id != workspace_id:
                from shared.infra.errors import ConflictError
                raise ConflictError(f"Workspace with slug '{input_dto.slug}' already exists")
            workspace.slug = input_dto.slug

        workspace.updated_at = datetime.now(UTC)
        saved = await self._workspace_repo.save(workspace)

        await self._outbox.write(
            aggregate_type="workspace",
            aggregate_id=saved.id,
            event_type="workspace.updated.v1",
            payload={"name": saved.name, "slug": saved.slug},
            routing_key="workspace.updated.v1",
            idempotency_key=f"identity:workspace.updated.v1:{saved.id}",
        )

        return UpdateWorkspaceOutput(
            id=saved.id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class InviteUserUseCase:

    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        invite_repo: WorkspaceInviteRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._workspace_repo = workspace_repo
        self._invite_repo = invite_repo
        self._outbox = outbox

    async def execute(self, input_dto: InviteUserInput) -> InviteUserOutput:
        workspace = await self._workspace_repo.get_by_id(input_dto.workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError(input_dto.workspace_id)

        existing = await self._invite_repo.get_by_workspace_and_email(
            input_dto.workspace_id, input_dto.email
        )
        if existing and existing.status == InviteStatus.pending:
            raise ConflictError("A pending invite already exists for this email")

        expires_at = datetime.now(UTC) + timedelta(days=7)
        invite = WorkspaceInvite(
            workspace_id=input_dto.workspace_id,
            email=input_dto.email,
            role=input_dto.role,
            token_hash="",
            invited_by_user_id=input_dto.invited_by_user_id,
            expires_at=expires_at,
        )
        saved = await self._invite_repo.save(invite)

        await self._outbox.write(
            aggregate_type="workspace_invite",
            aggregate_id=saved.id,
            event_type="workspace.invite_created.v1",
            payload={
                "workspace_id": str(saved.workspace_id),
                "email": saved.email,
                "role": saved.role.value,
            },
            routing_key="workspace.invite_created.v1",
            idempotency_key=f"identity:workspace.invite_created.v1:{saved.id}",
        )

        return InviteUserOutput(
            id=saved.id,
            workspace_id=saved.workspace_id,
            email=saved.email,
            role=saved.role,
            status=saved.status,
            expires_at=saved.expires_at,
            created_at=saved.created_at,
        )


class ListWorkspacesUseCase:

    def __init__(self, workspace_repo: WorkspaceRepository) -> None:
        self._workspace_repo = workspace_repo

    async def execute(self, input_dto: ListWorkspacesInput) -> list[ListWorkspacesOutput]:
        workspaces = await self._workspace_repo.list_all()
        return [ListWorkspacesOutput(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            status=workspace.status,
            created_at=workspace.created_at,
        ) for workspace in workspaces]


class LoginUseCase:

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, input_dto: LoginInput) -> LoginOutput:
        user = await self._user_repo.get_by_email(input_dto.email)
        if not user or not verify_password(input_dto.password, user.password):
            from modules.identity.domain.errors import InvalidCredentialsError
            raise InvalidCredentialsError("Invalid credentials")

        token = base64.b64encode(str(user.id).encode()).decode()
        return LoginOutput(
            token=token,
            user={"id": str(user.id), "email": user.email},
        )


class RegisterUseCase:

    def __init__(
        self,
        user_repo: UserRepository,
        workspace_repo: WorkspaceRepository,
        member_repo: WorkspaceMemberRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._user_repo = user_repo
        self._workspace_repo = workspace_repo
        self._member_repo = member_repo
        self._outbox = outbox

    async def execute(self, input_dto: RegisterInput) -> RegisterOutput:
        password_hash = hash_password(input_dto.password)
        user = User(email=input_dto.email, password=password_hash)
        saved_user = await self._user_repo.save(user)

        await self._outbox.write(
            aggregate_type="user",
            aggregate_id=saved_user.id,
            event_type="user.created.v1",
            payload={"email": saved_user.email},
            routing_key="user.created.v1",
            idempotency_key=f"identity:user.created.v1:{saved_user.id}",
        )

        workspace = Workspace(
            name=input_dto.workspace_name,
            slug=input_dto.workspace_name.lower().replace(" ", "-"),
        )
        saved_workspace = await self._workspace_repo.save(workspace)

        await self._outbox.write(
            aggregate_type="workspace",
            aggregate_id=saved_workspace.id,
            event_type="workspace.created.v1",
            payload={"name": saved_workspace.name, "slug": saved_workspace.slug},
            routing_key="workspace.created.v1",
            idempotency_key=f"identity:workspace.created.v1:{saved_workspace.id}",
        )

        member = WorkspaceMember(
            user_id=saved_user.id,
            workspace_id=saved_workspace.id,
            role=MemberRole.owner,
            joined_at=datetime.now(UTC),
        )
        await self._member_repo.save(member)

        await self._outbox.write(
            aggregate_type="workspace_member",
            aggregate_id=member.id,
            event_type="workspace.member_added.v1",
            payload={
                "user_id": str(member.user_id),
                "workspace_id": str(member.workspace_id),
                "role": member.role.value,
            },
            routing_key="workspace.member_added.v1",
            idempotency_key=f"identity:workspace.member_added.v1:{member.id}",
        )

        token = base64.b64encode(str(saved_user.id).encode()).decode()
        return RegisterOutput(
            token=token,
            user={"id": str(saved_user.id), "email": saved_user.email},
        )


class GetWorkspaceUseCase:

    def __init__(self, workspace_repo: WorkspaceRepository) -> None:
        self._workspace_repo = workspace_repo

    async def execute(self, input_dto: GetWorkspaceInput) -> GetWorkspaceOutput | None:
        workspace = await self._workspace_repo.get_by_id(input_dto.workspace_id)
        if not workspace:
            return None
        return GetWorkspaceOutput(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            status=workspace.status,
            created_at=workspace.created_at,
        )


class ListMembersUseCase:

    def __init__(self, member_repo: WorkspaceMemberRepository) -> None:
        self._member_repo = member_repo

    async def execute(self, input_dto: ListMembersInput) -> list[ListMembersOutput]:
        members = await self._member_repo.list_by_workspace(input_dto.workspace_id)
        return [ListMembersOutput(
            id=m.id,
            user_id=m.user_id,
            workspace_id=m.workspace_id,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
        ) for m in members]


class ListInvitesUseCase:

    def __init__(self, invite_repo: WorkspaceInviteRepository) -> None:
        self._invite_repo = invite_repo

    async def execute(self, input_dto: ListInvitesInput) -> list[ListInvitesOutput]:
        invites = await self._invite_repo.list_by_workspace(input_dto.workspace_id)
        return [ListInvitesOutput(
            id=i.id,
            workspace_id=i.workspace_id,
            email=i.email,
            role=i.role,
            status=i.status,
            expires_at=i.expires_at,
            created_at=i.created_at,
        ) for i in invites]


class GetUserUseCase:

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, input_dto: GetUserInput) -> GetUserOutput | None:
        user = await self._user_repo.get_by_id(input_dto.user_id)
        if not user:
            return None
        return GetUserOutput(
            id=user.id,
            email=user.email,
            status=user.status,
            created_at=user.created_at,
        )


class GetCurrentUserUseCase:

    async def execute(self, input_dto: GetCurrentUserInput) -> GetCurrentUserOutput:
        return GetCurrentUserOutput(email="customer@gmail.com", name=None)
