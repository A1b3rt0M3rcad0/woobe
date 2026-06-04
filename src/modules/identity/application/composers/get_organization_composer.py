from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.identity.infra.repositories import SQLAlchemyOrganizationRepository
from modules.identity.service.use_cases import GetOrganizationUseCase
from modules.identity.presentation.controllers.get_organization_controller import GetOrganizationController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_organization_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyOrganizationRepository(uow)
    use_case = GetOrganizationUseCase(repo)
    controller = GetOrganizationController(use_case)
    return TransactionalHandler(uow, controller.handle)
