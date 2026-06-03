from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.domain.repositories import (
    OrganizationInviteRepository,
    OrganizationMemberRepository,
    OrganizationRepository,
    UserRepository,
)
from modules.identity.infra.repositories import (
    SQLAlchemyOrganizationInviteRepository,
    SQLAlchemyOrganizationMemberRepository,
    SQLAlchemyOrganizationRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
)
from modules.identity.service.use_cases import (
    AddMemberToOrganizationUseCase,
    CreateOrganizationUseCase,
    CreateUserUseCase,
    InviteUserUseCase,
)
from shared.domain.events import OutboxEventWriter


def get_create_user_use_case(session: AsyncSession) -> CreateUserUseCase:
    user_repo: UserRepository = SQLAlchemyUserRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return CreateUserUseCase(user_repo, outbox)


def get_create_organization_use_case(session: AsyncSession) -> CreateOrganizationUseCase:
    org_repo: OrganizationRepository = SQLAlchemyOrganizationRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return CreateOrganizationUseCase(org_repo, outbox)


def get_add_member_use_case(session: AsyncSession) -> AddMemberToOrganizationUseCase:
    org_repo: OrganizationRepository = SQLAlchemyOrganizationRepository(session)
    user_repo: UserRepository = SQLAlchemyUserRepository(session)
    member_repo: OrganizationMemberRepository = SQLAlchemyOrganizationMemberRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return AddMemberToOrganizationUseCase(org_repo, user_repo, member_repo, outbox)


def get_invite_user_use_case(session: AsyncSession) -> InviteUserUseCase:
    org_repo: OrganizationRepository = SQLAlchemyOrganizationRepository(session)
    invite_repo: OrganizationInviteRepository = SQLAlchemyOrganizationInviteRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return InviteUserUseCase(org_repo, invite_repo, outbox)


def get_user_by_id_use_case(session: AsyncSession):
    user_repo: UserRepository = SQLAlchemyUserRepository(session)
    return _GetUserByIdUseCase(user_repo)


class _GetUserByIdUseCase:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: UUID):
        from modules.identity.domain.errors import UserNotFoundError
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user


def get_update_organization_use_case(session: AsyncSession) -> "UpdateOrganizationUseCase":
    from modules.identity.service.use_cases import UpdateOrganizationUseCase
    org_repo: OrganizationRepository = SQLAlchemyOrganizationRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return UpdateOrganizationUseCase(org_repo, outbox)


def get_organization_repo(session: AsyncSession) -> OrganizationRepository:
    return SQLAlchemyOrganizationRepository(session)


def get_member_repo(session: AsyncSession) -> OrganizationMemberRepository:
    return SQLAlchemyOrganizationMemberRepository(session)


def get_invite_repo(session: AsyncSession) -> OrganizationInviteRepository:
    return SQLAlchemyOrganizationInviteRepository(session)
