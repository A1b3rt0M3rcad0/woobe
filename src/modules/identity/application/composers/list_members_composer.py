from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyOrganizationMemberRepository
from modules.identity.service.use_cases import ListMembersUseCase
from modules.identity.presentation.controllers.list_members_controller import ListMembersController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_members_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    member_repo = SQLAlchemyOrganizationMemberRepository(uow)
    use_case = ListMembersUseCase(member_repo)
    controller = ListMembersController(use_case)
    return TransactionalHandler(uow, controller.handle)
