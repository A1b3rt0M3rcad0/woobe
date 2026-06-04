from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import (
    SQLAlchemyOrganizationMemberRepository,
    SQLAlchemyOrganizationRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUserRepository,
)
from modules.identity.service.use_cases import RegisterUseCase
from modules.identity.presentation.controllers.register_controller import RegisterController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def register_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    user_repo = SQLAlchemyUserRepository(uow)
    org_repo = SQLAlchemyOrganizationRepository(uow)
    member_repo = SQLAlchemyOrganizationMemberRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = RegisterUseCase(user_repo, org_repo, member_repo, outbox)
    controller = RegisterController(use_case)
    return TransactionalHandler(uow, controller.handle)
