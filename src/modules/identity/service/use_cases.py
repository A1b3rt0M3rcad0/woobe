from datetime import UTC, datetime, timedelta

from modules.identity.domain.entities import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
    User,
)
from modules.identity.domain.enums import InviteStatus
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
from modules.identity.service.dtos import (
    AddMemberInput,
    AddMemberOutput,
    CreateOrganizationInput,
    CreateOrganizationOutput,
    CreateUserInput,
    CreateUserOutput,
    InviteUserInput,
    InviteUserOutput,
)
from shared.domain.errors import ConflictError
from shared.domain.events import OutboxEventWriter
from shared.infra.crypto import hash_password


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
            event_type="user.created",
            payload={"email": saved.email},
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
            event_type="organization.created",
            payload={"name": saved.name, "slug": saved.slug},
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
            event_type="organization.member_added",
            payload={
                "user_id": str(saved.user_id),
                "organization_id": str(saved.organization_id),
                "role": saved.role.value,
            },
        )

        return AddMemberOutput(
            id=saved.id,
            user_id=saved.user_id,
            organization_id=saved.organization_id,
            role=saved.role,
            status=saved.status,
            joined_at=saved.joined_at,
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
            token_hash="",  # caller should set a proper token
            invited_by_user_id=input_dto.invited_by_user_id,
            expires_at=expires_at,
        )
        saved = await self._invite_repo.save(invite)

        await self._outbox.write(
            aggregate_type="organization_invite",
            aggregate_id=saved.id,
            event_type="organization.invite_created",
            payload={
                "organization_id": str(saved.organization_id),
                "email": saved.email,
                "role": saved.role.value,
            },
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
