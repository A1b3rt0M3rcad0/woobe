from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.domain.errors import UserNotFoundError
from modules.identity.domain.repositories import UserRepository
from modules.identity.infra.repositories import (
    SQLAlchemyOrganizationMemberRepository,
    SQLAlchemyOrganizationRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
)
from modules.identity.service.dtos import CreateUserOutput
from modules.identity.service.use_cases import (
    AddMemberToOrganizationUseCase,
    CreateOrganizationUseCase,
    CreateUserUseCase,
)


def get_create_user_use_case(session: AsyncSession) -> CreateUserUseCase:
    return CreateUserUseCase(
        user_repo=SQLAlchemyUserRepository(session),
        outbox=SQLAlchemyOutboxEventWriter(session),
    )


def get_create_organization_use_case(
    session: AsyncSession,
) -> CreateOrganizationUseCase:
    return CreateOrganizationUseCase(
        org_repo=SQLAlchemyOrganizationRepository(session),
        outbox=SQLAlchemyOutboxEventWriter(session),
    )


def get_add_member_use_case(
    session: AsyncSession,
) -> AddMemberToOrganizationUseCase:
    return AddMemberToOrganizationUseCase(
        org_repo=SQLAlchemyOrganizationRepository(session),
        user_repo=SQLAlchemyUserRepository(session),
        member_repo=SQLAlchemyOrganizationMemberRepository(session),
        outbox=SQLAlchemyOutboxEventWriter(session),
    )


class GetUserByIdUseCase:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def execute(self, user_id: UUID) -> CreateUserOutput:
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return CreateUserOutput(
            id=user.id,
            email=user.email,
            status=user.status,
            created_at=user.created_at,
        )


def get_user_by_id_use_case(session: AsyncSession) -> GetUserByIdUseCase:
    return GetUserByIdUseCase(
        user_repo=SQLAlchemyUserRepository(session),
    )
