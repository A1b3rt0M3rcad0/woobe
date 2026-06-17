import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID

from modules.identity.domain.entities import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
    User,
)
from modules.identity.domain.enums import InviteStatus, MemberRole
from modules.identity.domain.errors import (
    EmailAlreadyExistsError,
    OrganizationNotFoundError,
    UserNotFoundError,
)
from modules.identity.domain.repositories import (
    OrganizationInviteRepository,
    OrganizationMemberRepository,
    OrganizationRepository,
    UserRepository,
)
from modules.identity.application.dtos import (
    AddMemberInput,
    AddMemberOutput,
    CreateOrganizationInput,
    CreateOrganizationOutput,
    GetCurrentUserInput,
    GetCurrentUserOutput,
    GetOrganizationInput,
    GetOrganizationOutput,
    GetUserInput,
    GetUserOutput,
    InviteUserInput,
    InviteUserOutput,
    ListInvitesInput,
    ListInvitesOutput,
    ListMembersInput,
    ListMembersOutput,
    ListOrganizationsInput,
    ListOrganizationsOutput,
    LoginInput,
    LoginOutput,
    RegisterInput,
    RegisterOutput,
    UpdateOrganizationInput,
    UpdateOrganizationOutput,
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


class CreateOrganizationUseCase:

    def __init__(
        self,
        org_repo: OrganizationRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._org_repo = org_repo
        self._outbox = outbox

    async def execute(
        self, input_dto: CreateOrganizationInput
    ) -> CreateOrganizationOutput:
        existing = await self._org_repo.get_by_slug(input_dto.slug)
        if existing:
            raise ConflictError(f"Organization with slug '{input_dto.slug}' already exists")

        org = Organization(name=input_dto.name, slug=input_dto.slug)
        saved = await self._org_repo.save(org)

        await self._outbox.write(
            aggregate_type="organization",
            aggregate_id=saved.id,
            event_type="organization.created.v1",
            payload={"name": saved.name, "slug": saved.slug},
            routing_key="organization.created.v1",
            idempotency_key=f"identity:organization.created.v1:{saved.id}",
        )

        return CreateOrganizationOutput(
            id=saved.id,
            name=saved.name,
            slug=saved.slug,
            status=saved.status,
            created_at=saved.created_at,
        )


class AddMemberToOrganizationUseCase:

    def __init__(
        self,
        org_repo: OrganizationRepository,
        user_repo: UserRepository,
        member_repo: OrganizationMemberRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._org_repo = org_repo
        self._user_repo = user_repo
        self._member_repo = member_repo
        self._outbox = outbox

    async def execute(self, input_dto: AddMemberInput) -> AddMemberOutput:
        org = await self._org_repo.get_by_id(input_dto.organization_id)
        if not org:
            raise OrganizationNotFoundError(input_dto.organization_id)

        user = await self._user_repo.get_by_id(input_dto.user_id)
        if not user:
            raise UserNotFoundError(input_dto.user_id)

        existing_member = await self._member_repo.get_by_organization_and_user(
            input_dto.organization_id, input_dto.user_id
        )
        if existing_member:
            raise ConflictError("User is already a member of this organization")

        member = OrganizationMember(
            user_id=input_dto.user_id,
            organization_id=input_dto.organization_id,
            role=input_dto.role,
            joined_at=datetime.now(UTC),
        )
        saved = await self._member_repo.save(member)

        await self._outbox.write(
            aggregate_type="organization_member",
            aggregate_id=saved.id,
            event_type="organization.member_added.v1",
            payload={
                "user_id": str(saved.user_id),
                "organization_id": str(saved.organization_id),
                "role": saved.role.value,
            },
            routing_key="organization.member_added.v1",
            idempotency_key=f"identity:organization.member_added.v1:{saved.id}",
        )

        return AddMemberOutput(
            id=saved.id,
            user_id=saved.user_id,
            organization_id=saved.organization_id,
            role=saved.role,
            status=saved.status,
            joined_at=saved.joined_at,
        )


class UpdateOrganizationUseCase:

    def __init__(
        self,
        org_repo: OrganizationRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._org_repo = org_repo
        self._outbox = outbox

    async def execute(
        self, org_id: UUID, input_dto: UpdateOrganizationInput
    ) -> UpdateOrganizationOutput:
        org = await self._org_repo.get_by_id(org_id)
        if not org:
            raise OrganizationNotFoundError(org_id)

        if input_dto.name is not None:
            org.name = input_dto.name
        if input_dto.slug is not None:
            existing = await self._org_repo.get_by_slug(input_dto.slug)
            if existing and existing.id != org_id:
                from shared.infra.errors import ConflictError
                raise ConflictError(f"Organization with slug '{input_dto.slug}' already exists")
            org.slug = input_dto.slug

        org.updated_at = datetime.now(UTC)
        saved = await self._org_repo.save(org)

        await self._outbox.write(
            aggregate_type="organization",
            aggregate_id=saved.id,
            event_type="organization.updated.v1",
            payload={"name": saved.name, "slug": saved.slug},
            routing_key="organization.updated.v1",
            idempotency_key=f"identity:organization.updated.v1:{saved.id}",
        )

        return UpdateOrganizationOutput(
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
        org_repo: OrganizationRepository,
        invite_repo: OrganizationInviteRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._org_repo = org_repo
        self._invite_repo = invite_repo
        self._outbox = outbox

    async def execute(self, input_dto: InviteUserInput) -> InviteUserOutput:
        org = await self._org_repo.get_by_id(input_dto.organization_id)
        if not org:
            raise OrganizationNotFoundError(input_dto.organization_id)

        existing = await self._invite_repo.get_by_organization_and_email(
            input_dto.organization_id, input_dto.email
        )
        if existing and existing.status == InviteStatus.pending:
            raise ConflictError("A pending invite already exists for this email")

        expires_at = datetime.now(UTC) + timedelta(days=7)
        invite = OrganizationInvite(
            organization_id=input_dto.organization_id,
            email=input_dto.email,
            role=input_dto.role,
            token_hash="",
            invited_by_user_id=input_dto.invited_by_user_id,
            expires_at=expires_at,
        )
        saved = await self._invite_repo.save(invite)

        await self._outbox.write(
            aggregate_type="organization_invite",
            aggregate_id=saved.id,
            event_type="organization.invite_created.v1",
            payload={
                "organization_id": str(saved.organization_id),
                "email": saved.email,
                "role": saved.role.value,
            },
            routing_key="organization.invite_created.v1",
            idempotency_key=f"identity:organization.invite_created.v1:{saved.id}",
        )

        return InviteUserOutput(
            id=saved.id,
            organization_id=saved.organization_id,
            email=saved.email,
            role=saved.role,
            status=saved.status,
            expires_at=saved.expires_at,
            created_at=saved.created_at,
        )


class ListOrganizationsUseCase:

    def __init__(self, org_repo: OrganizationRepository) -> None:
        self._org_repo = org_repo

    async def execute(self, input_dto: ListOrganizationsInput) -> list[ListOrganizationsOutput]:
        orgs = await self._org_repo.list_all()
        return [ListOrganizationsOutput(
            id=o.id,
            name=o.name,
            slug=o.slug,
            status=o.status,
            created_at=o.created_at,
        ) for o in orgs]


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
        org_repo: OrganizationRepository,
        member_repo: OrganizationMemberRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._user_repo = user_repo
        self._org_repo = org_repo
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

        org = Organization(
            name=input_dto.organization_name,
            slug=input_dto.organization_name.lower().replace(" ", "-"),
        )
        saved_org = await self._org_repo.save(org)

        await self._outbox.write(
            aggregate_type="organization",
            aggregate_id=saved_org.id,
            event_type="organization.created.v1",
            payload={"name": saved_org.name, "slug": saved_org.slug},
            routing_key="organization.created.v1",
            idempotency_key=f"identity:organization.created.v1:{saved_org.id}",
        )

        member = OrganizationMember(
            user_id=saved_user.id,
            organization_id=saved_org.id,
            role=MemberRole.owner,
            joined_at=datetime.now(UTC),
        )
        await self._member_repo.save(member)

        await self._outbox.write(
            aggregate_type="organization_member",
            aggregate_id=member.id,
            event_type="organization.member_added.v1",
            payload={
                "user_id": str(member.user_id),
                "organization_id": str(member.organization_id),
                "role": member.role.value,
            },
            routing_key="organization.member_added.v1",
            idempotency_key=f"identity:organization.member_added.v1:{member.id}",
        )

        token = base64.b64encode(str(saved_user.id).encode()).decode()
        return RegisterOutput(
            token=token,
            user={"id": str(saved_user.id), "email": saved_user.email},
        )


class GetOrganizationUseCase:

    def __init__(self, org_repo: OrganizationRepository) -> None:
        self._org_repo = org_repo

    async def execute(self, input_dto: GetOrganizationInput) -> GetOrganizationOutput | None:
        org = await self._org_repo.get_by_id(input_dto.organization_id)
        if not org:
            return None
        return GetOrganizationOutput(
            id=org.id,
            name=org.name,
            slug=org.slug,
            status=org.status,
            created_at=org.created_at,
        )


class ListMembersUseCase:

    def __init__(self, member_repo: OrganizationMemberRepository) -> None:
        self._member_repo = member_repo

    async def execute(self, input_dto: ListMembersInput) -> list[ListMembersOutput]:
        members = await self._member_repo.list_by_organization(input_dto.organization_id)
        return [ListMembersOutput(
            id=m.id,
            user_id=m.user_id,
            organization_id=m.organization_id,
            role=m.role,
            status=m.status,
            joined_at=m.joined_at,
        ) for m in members]


class ListInvitesUseCase:

    def __init__(self, invite_repo: OrganizationInviteRepository) -> None:
        self._invite_repo = invite_repo

    async def execute(self, input_dto: ListInvitesInput) -> list[ListInvitesOutput]:
        invites = await self._invite_repo.list_by_organization(input_dto.organization_id)
        return [ListInvitesOutput(
            id=i.id,
            organization_id=i.organization_id,
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
