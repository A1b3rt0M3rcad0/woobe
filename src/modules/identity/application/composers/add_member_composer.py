from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import (
    SQLAlchemyOrganizationMemberRepository,
    SQLAlchemyOrganizationRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
)
from modules.identity.service.use_cases import AddMemberToOrganizationUseCase
from modules.identity.presentation.controllers.add_member_controller import AddMemberController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def add_member_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    org_repo = SQLAlchemyOrganizationRepository(uow)
    user_repo = SQLAlchemyUserRepository(uow)
    member_repo = SQLAlchemyOrganizationMemberRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = AddMemberToOrganizationUseCase(org_repo, user_repo, member_repo, outbox)
    controller = AddMemberController(use_case)
    return TransactionalHandler(uow, controller.handle)
